# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0-or-later
# 월하의 야상곡 얼티메이트 한글 패처 - https://github.com/kanx030/sotn-ultimate-ps1-kr
"""월하의 야상곡 얼티메이트 한글 패처 - 핵심 처리 (화면과 따로, 명령줄 시험에도 씀).

받는 것: 원본 SOTN Ultimate (PS1 Version) v1.4 이미지, 또는 예전에 만든 한글판 이미지.
형식: bin/cue, cue 없는 bin, CHD (chdman 으로 풀어서 확인), 2352 바이트 섹터로 된 .iso/.img.
원본이면 원본->최신 패치, 예전 한글판이면 그 판->최신 업데이트 패치를 고른다 (patch/versions.json).
"""
import ctypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import zlib

CHUNK = 4 * 1024 * 1024
VERSION = "v2.0.1"
DEFAULT_NAME = "SOTN Ultimate (Korean)"
CUE_TEXT = 'FILE "{name}.bin" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n'


class Cancelled(Exception):
    pass


class PatchError(Exception):
    pass


class AlreadyLatest(PatchError):
    pass


# ---------------------------------------------------------------- 경로
def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def resource(name):
    return os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), name)


def tool_path(name):
    for c in (resource(os.path.join("tools", name)), os.path.join(app_dir(), "tools", name),
              os.path.join(app_dir(), name)):
        if os.path.isfile(c):
            return c
    raise PatchError(f"도구 파일 {name} 을(를) 찾을 수 없습니다.")


def patch_path(fname):
    p = os.path.join(app_dir(), "patch", fname)
    if not os.path.isfile(p):
        raise PatchError(f"패치 파일이 없습니다:\n{p}\n\n패처 exe 옆의 patch 폴더에 패치 파일이 있어야 합니다.")
    return p


# ---------------------------------------------------------------- 알려진 이미지 (patch/versions.json)
_DB = None


def db():
    """{'target': {size,crc32,sha256,md5}, 'images': [{kind:'original'|'korean', label, title?, size, crc32,
    sha256, patch}]}"""
    global _DB
    if _DB is None:
        p = os.path.join(app_dir(), "patch", "versions.json")
        if not os.path.isfile(p):
            raise PatchError(f"패치 정보 파일이 없습니다:\n{p}")
        with open(p, encoding="utf-8") as f:
            _DB = json.load(f)
    return _DB


def sizes():
    return {i["size"] for i in db()["images"]} | {db()["target"]["size"]}


def original():
    return [i for i in db()["images"] if i["kind"] == "original"][0]


def expected_text():
    o, t = original(), db()["target"]
    ks = [i["label"] for i in db()["images"] if i["kind"] == "korean"]
    return (f"・원본: {o['title']}\n  크기 {o['size']:,} 바이트, CRC32 {o['crc32']}\n  SHA-256 {o['sha256']}\n"
            f"・업데이트할 수 있는 예전 한글판: {', '.join(ks)}\n"
            f"・최신 한글판 {VERSION}: CRC32 {t['crc32']}, MD5 {t['md5']}")


# ---------------------------------------------------------------- cue
def read_text(path):
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "cp949", "cp932", "latin-1"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("latin-1")


def parse_cue(path):
    base = os.path.dirname(os.path.abspath(path))
    files = []
    for line in read_text(path).splitlines():
        s = line.strip()
        m = re.match(r'FILE\s+"(.+)"\s+(\S+)$', s, re.I) or re.match(r'FILE\s+(\S+)\s+(\S+)$', s, re.I)
        if m:
            fp = m.group(1)
            if not os.path.isabs(fp):
                fp = os.path.join(base, fp)
            files.append(fp)
    if not files:
        raise PatchError("cue 파일에서 FILE 항목을 찾지 못했습니다.")
    for f in files:
        if not os.path.isfile(f):
            raise PatchError(f"cue 가 가리키는 파일이 없습니다:\n{f}")
    return files


# ---------------------------------------------------------------- 폴더 훑기 (크기로만 거름, 해시는 패치할 때)
def _dirs(folder):
    yield folder
    try:
        for n in sorted(os.listdir(folder)):
            p = os.path.join(folder, n)
            if os.path.isdir(p) and not n.startswith("_sotnkr"):
                yield p
    except OSError:
        pass


def scan_folder(folder):
    """후보 = {'src','kind'}. CHD 는 풀기 전에는 크기를 알 수 없어 모두 넣는다."""
    ok = sizes()
    cands = []
    for d in _dirs(folder):
        try:
            names = sorted(os.listdir(d))
        except OSError:
            continue
        refd = set()
        for n in names:
            p = os.path.join(d, n)
            if n.lower().endswith(".cue") and os.path.isfile(p):
                try:
                    fs = parse_cue(p)
                except Exception:
                    continue
                refd |= {os.path.normcase(os.path.abspath(f)) for f in fs}
                if sum(os.path.getsize(f) for f in fs) in ok:
                    cands.append({"src": p, "kind": "bin + cue"})
        for n in names:
            p = os.path.join(d, n)
            low = n.lower()
            if not os.path.isfile(p):
                continue
            if low.endswith(".chd"):
                cands.append({"src": p, "kind": "CHD"})
            elif low.endswith((".bin", ".iso", ".img")) and os.path.normcase(os.path.abspath(p)) not in refd \
                    and os.path.getsize(p) in ok:
                cands.append({"src": p, "kind": "cue 없는 " + low[-3:]})
    return cands


def not_found_message(folder):
    return (f"이 폴더에서 원본이나 예전 한글판을 찾지 못했습니다.\n{folder}\n(하위 폴더는 1단계까지 찾습니다)\n\n"
            "찾는 것 (bin/cue, CHD, 2352 바이트 섹터 iso/img):\n" + expected_text())


# ---------------------------------------------------------------- 해시
def hash_files(paths, progress=None, cancel=None):
    total = sum(os.path.getsize(p) for p in paths) or 1
    done, crc, sha, md5 = 0, 0, hashlib.sha256(), hashlib.md5()
    for p in paths:
        with open(p, "rb") as f:
            while True:
                if cancel and cancel():
                    raise Cancelled()
                b = f.read(CHUNK)
                if not b:
                    break
                crc = zlib.crc32(b, crc)
                sha.update(b)
                md5.update(b)
                done += len(b)
                if progress:
                    progress(done / total)
    return {"size": done, "crc32": "%08X" % (crc & 0xFFFFFFFF), "sha256": sha.hexdigest().upper(),
            "md5": md5.hexdigest().upper()}


def identify(info):
    t = db()["target"]
    if (info["size"], info["sha256"]) == (t["size"], t["sha256"]):
        return {"kind": "latest", "label": f"한글판 {VERSION} (최신)"}
    for i in db()["images"]:
        if (info["size"], info["crc32"], info["sha256"]) == (i["size"], i["crc32"], i["sha256"]):
            return i
    return None


def unknown_message(info):
    s = f"지원하는 이미지가 아닙니다.\n\n고른 이미지: 크기 {info['size']:,} 바이트"
    if info.get("crc32"):
        s += f", CRC32 {info['crc32']}"
    s += "\n\n" + expected_text()
    if info["size"] == db()["target"]["size"]:
        s += ("\n\n한글판과 크기는 같지만 업데이트할 수 있는 판이 아닙니다 (11-13 이전 판 등).\n"
              f"원본 {original()['title']} 으로 새로 패치해 주세요.")
    return s


# ---------------------------------------------------------------- 외부 도구
NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def run_tool(args, cancel=None, on_output=None, poll=None):
    try:
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)
    except OSError as e:
        raise PatchError(f"{os.path.basename(args[0])} 를 실행하지 못했습니다 ({e.strerror}).\n"
                         "백신이 막았을 수 있습니다. 패처 폴더의 tools 폴더를 백신 예외에 넣어 주세요.")
    lines = []

    def reader():
        cur = bytearray()
        while True:
            c = proc.stdout.read(1)
            if not c:
                break
            if c in (b"\r", b"\n"):
                if cur:
                    s = cur.decode("utf-8", "replace")
                    lines.append(s)
                    if on_output:
                        on_output(s)
                    cur = bytearray()
            else:
                cur += c
        if cur:
            lines.append(cur.decode("utf-8", "replace"))

    th = threading.Thread(target=reader, daemon=True)
    th.start()
    while True:
        try:
            rc = proc.wait(timeout=0.3)
            break
        except subprocess.TimeoutExpired:
            if cancel and cancel():
                proc.kill()
                proc.wait()
                th.join(2)
                raise Cancelled()
            if poll:
                poll()
    th.join(5)
    return rc, lines


def _pct(stage, progress):
    def f(s):
        m = re.search(r"([\d.]+)%\s*complete", s)
        if m:
            progress(stage, float(m.group(1)) / 100)
    return f


# ---------------------------------------------------------------- 작업
def safe_name(name):
    name = re.sub(r'[\\/:*?"<>|]', "_", name).strip().rstrip(".")
    return name or DEFAULT_NAME


def outputs_for(out_dir, name, fmt):
    if fmt == "chd":
        return [os.path.join(out_dir, name + ".chd")]
    return [os.path.join(out_dir, name + ".bin"), os.path.join(out_dir, name + ".cue")]


def is_ascii(path):
    try:
        os.fspath(path).encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def _writable(d):
    try:
        os.makedirs(d, exist_ok=True)
        t = os.path.join(d, "_w.tmp")
        with open(t, "wb") as f:
            f.write(b"0")
        os.remove(t)
        return True
    except OSError:
        return False


def pick_tmp(near, need, log):
    """chdman 0.215 는 영문이 아닌 글자가 든 경로를 못 연다 -> 도구 작업은 영문만 있는 임시 폴더에서."""
    import tempfile
    tag = "_sotnkr_tmp_%d" % os.getpid()
    cands = []
    if is_ascii(near):
        cands.append(os.path.join(near, "_sotnkr_patch_tmp"))
    drive = os.path.splitdrive(os.path.abspath(near))[0]
    if drive:
        cands.append(os.path.join(drive + os.sep, tag))
    cands.append(os.path.join(os.environ.get("PUBLIC", r"C:\Users\Public"), tag))
    cands.append(os.path.join(tempfile.gettempdir(), tag))
    for c in cands:
        if not is_ascii(c):
            continue
        try:
            free = shutil.disk_usage(os.path.dirname(c)).free
        except OSError:
            continue
        if free < need:
            continue
        shutil.rmtree(c, ignore_errors=True)
        if _writable(c):
            log("작업 폴더: " + c)
            return c
    raise PatchError("작업용 임시 폴더를 만들 곳이 없습니다.\n"
                     f"영문으로만 된 경로에 빈 공간 약 {need / 2**30:.2f} GB 가 있는 드라이브가 필요합니다.")


def ascii_input(path, tmp, name):
    """도구에 넘길 입력 경로가 영문이 아니면 임시 폴더에 하드 링크(안 되면 복사)."""
    if is_ascii(path):
        return path
    dst = os.path.join(tmp, name)
    try:
        os.link(path, dst)
    except OSError:
        shutil.copyfile(path, dst)
    return dst


def long_path(p):
    p = os.path.abspath(p)
    if p.startswith("\\\\?\\"):
        return p
    if p.startswith("\\\\"):
        return "\\\\?\\UNC\\" + p[2:]
    return "\\\\?\\" + p


class ChdDll:
    r"""RomForge (https://github.com/sinjunyoung/RomForge, sinjunyoung, GPL-2.0) v2.0.4 의 chdman 래퍼 DLL.
    UTF-8 경로를 그대로 받아 한글 경로를 다룬다. 함수 (cdecl), 결과 0 성공 / -1 취소 / 1 오류:
      chdman_create_cd(input, output, compression, progress(int %), log(const char *))
      chdman_extract_cd(input, output, progress, log)     -- 트랙별 '(Track NN).bin' + cue 로 풂
      chdman_get_info(input, log)
      chdman_cancel()
    작업 폴더를 입력 파일 폴더로 바꾸고 \\?\ 를 붙인 전체 경로를 넘긴다 (RomForge 와 같게).
    tools\chdman.dll 이 없거나 실패하면 부르는 쪽이 chdman.exe 로 대신한다."""
    _inst, _tried, load_error = None, False, None
    _lock = threading.Lock()

    @classmethod
    def get(cls):
        if not cls._tried:
            cls._tried = True
            d = os.path.join(app_dir(), "tools")
            p = os.path.join(d, "chdman.dll")
            if os.path.isfile(p):
                try:
                    if hasattr(os, "add_dll_directory"):
                        os.add_dll_directory(d)
                    cls._inst = cls(ctypes.CDLL(p))
                except (OSError, AttributeError) as e:
                    cls.load_error = f"불러오기 실패: {e}"
            else:
                cls.load_error = "tools\\chdman.dll 없음"
        return cls._inst

    def __init__(self, lib):
        self.lib = lib
        self.PROG = ctypes.CFUNCTYPE(None, ctypes.c_int)
        self.LOG = ctypes.CFUNCTYPE(None, ctypes.c_char_p)
        c = ctypes.c_char_p
        lib.chdman_create_cd.argtypes = [c, c, c, self.PROG, self.LOG]
        lib.chdman_create_cd.restype = ctypes.c_int
        lib.chdman_extract_cd.argtypes = [c, c, self.PROG, self.LOG]
        lib.chdman_extract_cd.restype = ctypes.c_int
        lib.chdman_get_info.argtypes = [c, self.LOG]
        lib.chdman_get_info.restype = ctypes.c_int
        lib.chdman_cancel.argtypes = []
        lib.chdman_cancel.restype = None

    def _call(self, invoke, workdir, progress=None, cancel=None):
        lines, res = [], {}

        def on_log(m):
            if m:
                lines.append(m.decode("utf-8", "replace").rstrip())

        def on_prog(v):
            if progress:
                progress(max(0, min(100, v)) / 100)
        logcb, progcb = self.LOG(on_log), self.PROG(on_prog)

        def body():
            with ChdDll._lock:
                old = os.getcwd()
                try:
                    os.chdir(workdir)
                    res["rc"] = invoke(progcb, logcb)
                except Exception as e:  # noqa
                    res["rc"] = 1
                    lines.append(f"{type(e).__name__}: {e}")
                finally:
                    try:
                        os.chdir(old)
                    except OSError:
                        pass
        th = threading.Thread(target=body, daemon=True)
        th.start()
        cancelled = False
        while th.is_alive():
            th.join(0.3)
            if cancel and not cancelled and cancel():
                cancelled = True
                self.lib.chdman_cancel()
        th.join()
        if cancelled or res.get("rc") == -1:
            raise Cancelled()
        return res.get("rc", 1), lines

    def create_cd(self, cue, out_chd, progress=None, cancel=None):
        i, o = long_path(cue).encode("utf-8"), long_path(out_chd).encode("utf-8")
        return self._call(lambda pc, lc: self.lib.chdman_create_cd(i, o, None, pc, lc),
                          os.path.dirname(os.path.abspath(cue)), progress, cancel)

    def extract_cd(self, chd, out_cue, progress=None, cancel=None):
        i, o = long_path(chd).encode("utf-8"), long_path(out_cue).encode("utf-8")
        return self._call(lambda pc, lc: self.lib.chdman_extract_cd(i, o, pc, lc),
                          os.path.dirname(os.path.abspath(out_cue)), progress, cancel)

    def info(self, chd):
        i = long_path(chd).encode("utf-8")
        return self._call(lambda pc, lc: self.lib.chdman_get_info(i, lc), os.path.dirname(os.path.abspath(chd)))


def chd_sha1s(path):
    """CHD 머리글의 SHA1·Data SHA1 (DLL 로, 안 되면 chdman.exe). 못 읽으면 빈 집합."""
    txt = ""
    dll = ChdDll.get()
    if dll:
        try:
            rc, lines = dll.info(path)
            if rc == 0:
                txt = "\n".join(lines)
        except Cancelled:
            pass
    if not re.search(r"SHA1:\s*[0-9a-fA-F]{40}", txt) and is_ascii(os.path.abspath(path)):
        try:
            txt = subprocess.run([tool_path("chdman.exe"), "info", "-i", path], capture_output=True, text=True,
                                 stdin=subprocess.DEVNULL, creationflags=NO_WINDOW, timeout=120).stdout
        except Exception:  # noqa
            txt = ""
    return {m.lower() for m in re.findall(r"SHA1:\s*([0-9a-fA-F]{40})", txt)}


def run_patch(src, out_dir, name, fmt, log, progress, cancel, replace=False):
    """
    src: .cue / .bin / .iso / .img / .chd
    fmt: 'bincue' | 'chd' (새로 만들 때)
    replace: 예전 한글판이면 그 파일 자리에 같은 이름·형식으로 최신 판을 넣음 (원본이면 무시)
    돌려줌: (만든 파일 목록, 한 줄 설명)
    """
    name = safe_name(name)
    xdelta = tool_path("xdelta.exe")
    chdman = tool_path("chdman.exe")
    t = db()["target"]
    is_chd = src.lower().endswith(".chd")
    src_dir = os.path.dirname(os.path.abspath(src))
    dest_dir = src_dir if replace else out_dir
    if not os.path.isdir(out_dir):
        raise PatchError("저장할 폴더가 없습니다.")
    for d in ([src_dir] if replace else []) + [out_dir]:
        if not _writable(d):
            raise PatchError(f"이 폴더에 파일을 쓸 수 없습니다 (권한 또는 읽기 전용):\n{d}\n\n다른 폴더를 골라 주세요.")
    need = t["size"] * (3 if is_chd else 2) + (64 << 20)
    tmp = pick_tmp(dest_dir, need, log)
    if os.path.splitdrive(dest_dir)[0].lower() != os.path.splitdrive(tmp)[0].lower() and \
            shutil.disk_usage(dest_dir).free < t["size"] + (64 << 20):
        shutil.rmtree(tmp, ignore_errors=True)
        raise PatchError("저장 폴더의 드라이브에 빈 공간이 부족합니다 (약 0.8 GB 필요).")
    parts = []
    try:
        # 1) 이미지 준비
        if is_chd:
            log("CHD 를 푸는 중...")
            progress("CHD 풀기", 0)
            paths = None
            dll = ChdDll.get()
            if dll:
                xd = os.path.join(tmp, "x")
                os.makedirs(xd)
                rc, lines = dll.extract_cd(src, os.path.join(xd, "src.cue"), lambda f: progress("CHD 풀기", f), cancel)
                for l in lines[-6:]:
                    log("  chdman.dll: " + l)
                try:
                    if rc == 0:
                        paths = parse_cue(os.path.join(xd, "src.cue"))       # 트랙별 bin -> 아래에서 하나로 합침
                        log(f"  chdman.dll 로 풀었습니다 (트랙 {len(paths)}개).")
                except PatchError:
                    paths = None
                if not paths:
                    log(f"  chdman.dll 풀기 실패 (결과 {rc}) - chdman.exe 로 다시 합니다.")
                    shutil.rmtree(xd, ignore_errors=True)
            else:
                log(f"  chdman.dll 을 쓰지 않음 ({ChdDll.load_error}) - chdman.exe 사용")
            if not paths:
                cue0, bin0 = os.path.join(tmp, "src.cue"), os.path.join(tmp, "src.bin")
                rc, lines = run_tool([chdman, "extractcd", "-f", "-i", ascii_input(src, tmp, "in.chd"), "-o", cue0,
                                      "-ob", bin0], cancel, on_output=_pct("CHD 풀기", progress))
                if rc != 0 or not os.path.isfile(bin0):
                    for l in lines[-8:]:
                        log("  chdman: " + l)
                    raise PatchError("CHD 를 풀지 못했습니다 (chdman 오류).\n" + "\n".join(lines[-5:]))
                if os.path.exists(os.path.join(tmp, "in.chd")):
                    os.remove(os.path.join(tmp, "in.chd"))
                paths = [bin0]
        elif src.lower().endswith(".cue"):
            paths = parse_cue(src)
        else:
            paths = [src]
        size = sum(os.path.getsize(p) for p in paths)
        log(f"이미지 크기 {size:,} 바이트")
        if size not in sizes():
            raise PatchError(unknown_message({"size": size}))
        if len(paths) > 1:
            merged = os.path.join(tmp, "merged.bin")
            with open(merged, "wb") as o:
                for p in paths:
                    with open(p, "rb") as f:
                        shutil.copyfileobj(f, o, CHUNK)
            for p in paths:
                if os.path.dirname(os.path.abspath(p)).startswith(tmp):
                    os.remove(p)
            paths = [merged]
        srcbin = paths[0]

        # 2) 판 확인
        log("이미지 확인 중...")
        info = hash_files([srcbin], lambda f: progress("이미지 확인", f), cancel)
        log(f"CRC32 {info['crc32']} / SHA-256 {info['sha256']}")
        who = identify(info)
        if not who:
            raise PatchError(unknown_message(info))
        log(f"확인됨: {who['label']}")
        if who["kind"] == "latest":
            raise AlreadyLatest(f"이미 최신입니다. (한글판 {VERSION}) 따로 할 일이 없습니다.")
        if replace and who["kind"] != "korean":
            replace = False
            log("원본이므로 원본은 그대로 두고 새 파일을 만듭니다.")
        patch = patch_path(who["patch"])

        # 3) 패치
        out_bin = os.path.join(tmp, "result.bin")
        log(("업데이트 패치" if who["kind"] == "korean" else "한글 패치") + " 적용 중 (xdelta)...")
        progress("패치 적용", 0)

        def poll():
            try:
                progress("패치 적용", min(1.0, os.path.getsize(out_bin) / t["size"]))
            except OSError:
                pass
        rc, lines = run_tool([xdelta, "-d", "-f", "-B", "402653184", "-s", srcbin, patch, out_bin], cancel, poll=poll)
        if rc != 0:
            raise PatchError("패치 적용에 실패했습니다 (xdelta 오류).\n" + "\n".join(lines[-5:]))
        if os.path.dirname(srcbin) == tmp:
            os.remove(srcbin)

        # 4) 결과 확인
        log("결과 이미지 확인 중...")
        r = hash_files([out_bin], lambda f: progress("결과 확인", f), cancel)
        log(f"결과 CRC32 {r['crc32']} / MD5 {r['md5']}")
        if (r["size"], r["sha256"], r["md5"]) != (t["size"], t["sha256"], t["md5"]):
            raise PatchError("패치 결과가 예상 값과 다릅니다. 이미지나 패치 파일이 손상되었을 수 있습니다.")
        log(f"결과가 한글판 {VERSION} 과 정확히 같습니다.")

        # 5) 저장할 자리
        old = []
        if replace:
            base = os.path.splitext(os.path.basename(src))[0]
            if is_chd:
                fmt, finals = "chd", [src]
            elif src.lower().endswith(".cue"):
                fmt, finals = "bincue", outputs_for(src_dir, base, "bincue")
                old = parse_cue(src) + [src]
            else:
                fmt, finals = "bin", [src]                       # cue 없는 bin/iso/img: 그 파일만 바꿈
        else:
            finals = outputs_for(out_dir, name, fmt)
            for p in finals:
                if os.path.exists(p):
                    raise PatchError(f"같은 이름의 파일이 이미 있습니다:\n{p}\n\n다른 이름을 쓰거나 기존 파일을 옮겨 주세요.")

        # 6) 결과 파일 (.part 로 만든 뒤 마지막에 이름 바꿈)
        note = ""
        if fmt == "chd":
            tcue = os.path.join(tmp, "result.cue")
            with open(tcue, "w", encoding="utf-8", newline="\r\n") as f:
                f.write(CUE_TEXT.format(name="result"))
            log("CHD 로 압축하는 중 (chdman, 몇 분 걸릴 수 있습니다)...")
            progress("CHD 압축", 0)
            tchd = os.path.join(tmp, "out.chd")
            rc, lines = 1, []
            dll = ChdDll.get()
            if dll:
                rc, lines = dll.create_cd(tcue, tchd, lambda f: progress("CHD 압축", f), cancel)
                for l in lines[-6:]:
                    log("  chdman.dll: " + l)
                want = {x.lower() for x in t.get("chd_sha1", [])}
                got = chd_sha1s(tchd) if rc == 0 and os.path.isfile(tchd) else set()
                if rc == 0 and got and (not want or want & got):
                    log("  chdman.dll 로 압축했습니다. CHD SHA1 " + ", ".join(sorted(got)))
                else:
                    log(f"  chdman.dll 압축 실패 또는 SHA1 불일치 (결과 {rc}) - chdman.exe 로 다시 합니다.")
                    rc = 1
                    if os.path.exists(tchd):
                        os.remove(tchd)
            else:
                log(f"  chdman.dll 을 쓰지 않음 ({ChdDll.load_error}) - chdman.exe 사용")
            if rc != 0:
                progress("CHD 압축", 0)
                rc, lines = run_tool([chdman, "createcd", "-f", "-i", tcue, "-o", tchd], cancel,
                                     on_output=_pct("CHD 압축", progress))
            if rc == 0 and os.path.isfile(tchd):
                part = finals[0] + ".part"
                parts.append(part)
                shutil.move(tchd, part)
                moves = [(part, finals[0])]
            else:
                for l in lines[-8:]:
                    log("  chdman: " + l)
                log("CHD 압축에 실패해서, 확인이 끝난 BIN/CUE 로 대신 저장합니다.")
                d0 = os.path.dirname(finals[0])
                b0 = os.path.splitext(os.path.basename(finals[0]))[0] + (f" ({VERSION})" if replace else "")
                finals = outputs_for(d0, b0, "bincue")
                for p in finals:
                    if os.path.exists(p):
                        raise PatchError("CHD 만들기에 실패했고, BIN/CUE 로 저장할 자리에도 같은 이름의 파일이 있습니다:\n" + p)
                fmt = "bincue"
                note = ("\n\nCHD 압축은 실패해서 BIN/CUE 로 저장했습니다"
                        + (" (원래 CHD 는 그대로 두었습니다)." if replace else ".")
                        + "\n백신이 chdman.exe 를 막았거나 폴더 권한 문제일 수 있습니다.")
                replace = False
        if fmt != "chd":
            binp = finals[0]
            parts.append(binp + ".part")
            shutil.move(out_bin, binp + ".part")
            moves = [(binp + ".part", binp)]
            if fmt == "bincue":
                parts.append(finals[1] + ".part")
                with open(finals[1] + ".part", "w", encoding="utf-8", newline="\r\n") as f:
                    f.write(CUE_TEXT.format(name=os.path.splitext(os.path.basename(binp))[0]))
                moves.append((finals[1] + ".part", finals[1]))
        keep = {os.path.normcase(os.path.abspath(f)) for f in finals}
        for p in (old if replace else []):                                            # 예전 판 파일 중 새 이름과 다른 것 (예: 이름이 다른 bin)
            if os.path.normcase(os.path.abspath(p)) not in keep and os.path.exists(p):
                os.remove(p)
                log("예전 파일 지움: " + p)
        for a, b in moves:
            os.replace(a, b)
        progress("완료", 1)
        what = ("예전 한글판을 최신 판으로 바꿨습니다." if replace else "한글판을 만들었습니다.") + note
        return finals, what
    except BaseException:
        for p in parts:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass
        raise
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
