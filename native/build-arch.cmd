@rem nguyenphi37
@echo off
setlocal
cd /d "%~dp0"
set "ARCH=%~1"
set "VCBAT=%~2"
set "DETTARGET=%~3"
set "DET=%~dp0..\third_party\Detours-4.0.1"
set "INC=%DET%\src"
call "%VCBAT%" || exit /b 1
if not exist "build\%ARCH%" mkdir "build\%ARCH%"
if not exist "%DET%\lib.%DETTARGET%\detours.lib" (
  pushd "%DET%\src"
  nmake /nologo DETOURS_TARGET_PROCESSOR=%DETTARGET%
  if errorlevel 1 exit /b 1
  popd
)
cl /nologo /std:c++17 /EHsc /W3 /MT /O2 /DUNICODE /D_UNICODE /I "%INC%" /c DueHook.cpp /Fo:build\%ARCH%\DueHook.obj || exit /b 1
link /nologo /DLL /OUT:build\%ARCH%\DueHook.dll build\%ARCH%\DueHook.obj "%DET%\lib.%DETTARGET%\detours.lib" shell32.lib ole32.lib propsys.lib uuid.lib kernel32.lib user32.lib /EXPORT:DetourFinishHelperProcess,@1,NONAME || exit /b 1
cl /nologo /std:c++17 /EHsc /W3 /MT /O2 /DUNICODE /D_UNICODE /I "%INC%" /c DueLaunch.cpp /Fo:build\%ARCH%\DueLaunch.obj || exit /b 1
link /nologo /SUBSYSTEM:WINDOWS /OUT:build\%ARCH%\DueLaunch.exe build\%ARCH%\DueLaunch.obj shell32.lib ole32.lib kernel32.lib user32.lib || exit /b 1
cl /nologo /std:c++17 /EHsc /W3 /MT /O2 /DUNICODE /D_UNICODE /c DueProbe.cpp /Fo:build\%ARCH%\DueProbe.obj || exit /b 1
link /nologo /SUBSYSTEM:WINDOWS /OUT:build\%ARCH%\DueProbe.exe build\%ARCH%\DueProbe.obj shell32.lib ole32.lib kernel32.lib user32.lib || exit /b 1
exit /b 0
