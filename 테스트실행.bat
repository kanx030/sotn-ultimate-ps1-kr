@echo off
rem 최신 검수 빌드를 테스트 설정(사용자 설정과 분리)으로 실행
for /f "delims=" %%f in ('dir /b /o-d "E:\SOTNKR\work\build\test*.cue"') do (
  set CUE=%%f
  goto run
)
:run
start "" "I:\AttractMode\emulators\RetroArch\retroarch.exe" --config "E:\SOTNKR\test\ra.cfg" -L "I:\AttractMode\emulators\RetroArch\cores\swanstation_libretro.dll" "E:\SOTNKR\work\build\%CUE%"
