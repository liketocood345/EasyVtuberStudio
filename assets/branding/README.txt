Application branding for THA4 Load Preview / EasyVtuber fork.

Files:
  app-icon-source.png  Source artwork (user-provided white wolf chibi).
  app-icon-source.ico  Multi-size Windows icon for exe and shortcuts.

Regenerate ICO after editing PNG (requires Python venv from DEPLOY [1] or [2]):
  <REPO>\addons\face_puppeteer\venv\Scripts\python.exe packaging\make_app_icon.py
  or: <REPO>\workspace\student_venv\Scripts\python.exe packaging\make_app_icon.py

Used by:
  packaging\build_launchers.ps1  (--icon for EasyVtuberStudio.exe only; THA4Train.exe has no custom icon)
  packaging\load_preview.spec    (PyInstaller alternate route only)

Primary release plan:
  plans\PORTABLE_RELEASE.plan.md
