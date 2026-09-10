@echo off

:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
::   SET USER INPUT HERE, DONT FORGET THE BRACKETS!! ""              ::
:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
SET user_name="mhagen"
SET user_pool="pool0009"
:: If needed you can add a custom python path here (if python was not installed regularly)
:: This is only needed if the file wont run normally
SET custom_python_path="C:\PBF-MeshGraphNet\.venv\Scripts\python.exe"

SET defaults_0="2" &:: default priority 1 = normal, 2 = lower
SET defaults_1="2" &:: default machine 0 = local, 1 = uxcs1, 2 = uxcs2
SET defaults_2="0" &:: default answer to machine change 1 = yes, 0 = no
SET defaults_3="1" &:: default number of CPU's
SET defaults_4="1" &:: default answer to tokens agree 1 = yes, 2 = no
SET defaults_5="2" &:: default abaqus version 1 = most recent version
SET defaults_6="0" &:: default GPU acceleration answer
SET defaults_7="0" &:: default answer to zip 1 = yes, 0 = no
SET defaults_8="1" &:: default answer to mail 1 = yes, 0 = no
:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
::   check your pool with command 'pwd -P' on uxcs                   ::
::   code continues here, no changes necessary                       ::
:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

:: this part is needed because sometimes the Q: drive is mapped but not connected yet
if exist "\\cockpit2@SSL\DavWWWRoot\groups\312\Documents\NURD\" (
    GOTO:setup
) else explorer.exe "\\cockpit2@SSL\DavWWWRoot\groups\312\Documents\NURD\"

PING localhost -n 4 >NUL

:setup
SET defaults="%defaults_0%%defaults_1%%defaults_2%%defaults_3%%defaults_4%%defaults_5%%defaults_6%%defaults_7%%defaults_8%" 
SET script_location="C:\PBF-MeshGraphNet\dataset_generation\nurd\NURD.py"

IF NOT %custom_python_path% == "" GOTO call_function

:: This part searches for the local python install
SETLOCAL ENABLEDELAYEDEXPANSION
FOR /F "tokens=* USEBACKQ" %%F IN (`where python`) DO (
  Echo.%%F | findstr /C:"3">nul && (
    call "%%F" %script_location% "%cd%" %user_name% %user_pool% %defaults%
	GOTO:eof
	
  )
  Echo."Please install python 3"
  GOTO:eof
  
)

:call_function
call %custom_python_path% %script_location% "%cd%" %user_name% %user_pool% %defaults%
GOTO:eof

ENDLOCAL
