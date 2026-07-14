REM
pyinstaller --onefile  --noconsole --add-data "GumInspect.ui;." --add-data "database.csv;." GumInspect.py
copy "D:\PROJETOS\Silvio_de_Luca\Odonto\QtDesigner\GumInspect.ui"    "D:\PROJETOS\Silvio_de_Luca\Odonto\QtDesigner\dist"
copy "D:\PROJETOS\Silvio_de_Luca\Odonto\QtDesigner\GumInspect_ui.py" "D:\PROJETOS\Silvio_de_Luca\Odonto\QtDesigner\dist"
copy "D:\PROJETOS\Silvio_de_Luca\Odonto\QtDesigner\database.csv"     "D:\PROJETOS\Silvio_de_Luca\Odonto\QtDesigner\dist"