@echo off
setlocal
cd /d "%~dp0"
echo ========================================
echo Blaugrana Android APK builder
echo ========================================
where node >nul 2>nul || (echo ERROR: Install Node.js 22 or newer first.& pause & exit /b 1)
where npm >nul 2>nul || (echo ERROR: npm was not found.& pause & exit /b 1)
if not exist android (call npm install && if errorlevel 1 goto fail
  call npx cap add android && if errorlevel 1 goto fail
) else (
  call npm install && if errorlevel 1 goto fail
)
call npx cap sync android
if errorlevel 1 goto fail
if not exist android\local.properties echo NOTE: If Gradle cannot find the SDK, open android in Android Studio and install an Android SDK.
cd android
call gradlew.bat assembleDebug
if errorlevel 1 goto fail
cd ..
if exist android\app\build\outputs\apk\debug\app-debug.apk (
  copy /y android\app\build\outputs\apk\debug\app-debug.apk Blaugrana-debug.apk >nul
  echo.
  echo SUCCESS: %CD%\Blaugrana-debug.apk
  echo This is a debug APK for testing and direct installation.
) else (
  echo Build completed but the expected APK was not found. Check Android Studio/Gradle output.
)
pause
exit /b 0
:fail
echo.
echo Build failed. Install Android Studio and Android SDK, then open the android folder once to complete setup.
pause
exit /b 1
