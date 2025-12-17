@echo off
REM ============================================================================
REM Script de packaging Liris pour Windows
REM Crée une archive ZIP distribuable après compilation PyInstaller
REM ============================================================================

setlocal enabledelayedexpansion

echo.
echo ========================================
echo   PACKAGING LIRIS POUR WINDOWS
echo ========================================
echo.

REM Définir les variables
set APP_NAME=Liris
set VERSION=1.0.0
set DIST_DIR=dist
set PACKAGE_NAME=%APP_NAME%-v%VERSION%-Windows-x64

REM Vérifier que l'exécutable existe
if not exist "%DIST_DIR%\%APP_NAME%.exe" (
    echo [ERREUR] L'executable %APP_NAME%.exe n'existe pas dans %DIST_DIR%\
    echo.
    echo Veuillez d'abord compiler avec:
    echo   pyinstaller Liris.spec --clean
    echo.
    pause
    exit /b 1
)

echo [OK] Executable trouve: %DIST_DIR%\%APP_NAME%.exe
echo.

REM Créer le dossier de package
echo Creation du dossier de package...
if exist "%DIST_DIR%\%PACKAGE_NAME%" rmdir /s /q "%DIST_DIR%\%PACKAGE_NAME%"
mkdir "%DIST_DIR%\%PACKAGE_NAME%"

REM Copier l'exécutable
echo Copie de l'executable...
copy "%DIST_DIR%\%APP_NAME%.exe" "%DIST_DIR%\%PACKAGE_NAME%\" >nul
echo [OK] Executable copie

REM Créer un fichier README
echo Creation du README...
(
echo LIRIS - Application IA Collaborative
echo ====================================
echo.
echo Version: %VERSION%
echo Plateforme: Windows x64
echo.
echo INSTALLATION:
echo 1. Extraire tous les fichiers de l'archive
echo 2. Double-cliquer sur Liris.exe
echo.
echo PREREQUIS:
echo - Windows 10 ou superieur
echo - Aucune installation requise
echo.
echo DESINSTALLATION:
echo Supprimer simplement le dossier complet.
echo.
echo SUPPORT:
echo Pour signaler un bug ou obtenir de l'aide:
echo [Votre email ou site web]
echo.
echo ====================================
echo Copyright ^(c^) 2024 - Tous droits reserves
) > "%DIST_DIR%\%PACKAGE_NAME%\README.txt"
echo [OK] README cree

REM Créer un fichier de licence (optionnel)
echo Creation du fichier LICENSE...
(
echo MIT License
echo.
echo Copyright ^(c^) 2024
echo.
echo Permission is hereby granted, free of charge, to any person obtaining a copy
echo of this software and associated documentation files ^(the "Software"^), to deal
echo in the Software without restriction...
echo.
echo [Ajoutez votre licence complete ici]
) > "%DIST_DIR%\%PACKAGE_NAME%\LICENSE.txt"
echo [OK] LICENSE cree

REM Vérifier si 7-Zip est installé
set SEVENZIP=
if exist "C:\Program Files\7-Zip\7z.exe" set SEVENZIP=C:\Program Files\7-Zip\7z.exe
if exist "C:\Program Files (x86)\7-Zip\7z.exe" set SEVENZIP=C:\Program Files (x86)\7-Zip\7z.exe

REM Créer l'archive
echo.
echo Creation de l'archive...
if defined SEVENZIP (
    echo Utilisation de 7-Zip...
    "%SEVENZIP%" a -tzip "%DIST_DIR%\%PACKAGE_NAME%.zip" "%DIST_DIR%\%PACKAGE_NAME%\*" >nul
    if !errorlevel! equ 0 (
        echo [OK] Archive ZIP creee avec 7-Zip
    ) else (
        echo [ERREUR] Echec de la creation avec 7-Zip
    )
) else (
    echo 7-Zip non trouve, utilisation de PowerShell...
    powershell -command "Compress-Archive -Path '%DIST_DIR%\%PACKAGE_NAME%\*' -DestinationPath '%DIST_DIR%\%PACKAGE_NAME%.zip' -Force"
    if !errorlevel! equ 0 (
        echo [OK] Archive ZIP creee avec PowerShell
    ) else (
        echo [ERREUR] Echec de la creation avec PowerShell
    )
)

REM Afficher les informations
echo.
echo ========================================
echo   PACKAGING TERMINE
echo ========================================
echo.
echo Fichiers generes:
echo   - Dossier: %DIST_DIR%\%PACKAGE_NAME%\
echo   - Archive: %DIST_DIR%\%PACKAGE_NAME%.zip
echo.

REM Afficher la taille des fichiers
for %%F in ("%DIST_DIR%\%APP_NAME%.exe") do echo Taille executable: %%~zF octets
for %%F in ("%DIST_DIR%\%PACKAGE_NAME%.zip") do echo Taille archive:    %%~zF octets
echo.

REM Ouvrir le dossier dist
echo Ouverture du dossier de distribution...
explorer "%DIST_DIR%"

echo.
echo Vous pouvez maintenant distribuer le fichier:
echo   %PACKAGE_NAME%.zip
echo.
pause