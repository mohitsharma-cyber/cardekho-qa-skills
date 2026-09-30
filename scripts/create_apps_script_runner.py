import json
import pandas as pd

df = pd.read_csv('output/cleaned_google_sheet/Updated_CarDekho_DeepLinks.csv')

rows = []
for _, r in df.iterrows():
    rows.append([
        int(r['S.No']),
        str(r['Type / Feature']),
        str(r['Original URL']),
        str(r['Updated / Canonical URL']),
        str(r['Validation Status']),
        str(r['HTTP Code']),
        str(r['View']),
        str(r['QA Status Android']),
        str(r['Issue / Audit Remarks']) if pd.notnull(r['Issue / Audit Remarks']) else ''
    ])

js_rows = json.dumps(rows, ensure_ascii=False)

script_code = f"""function importCleanedDeepLinks() {{
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheetName = 'Updated_Deep_Links_Live';
  var sheet = ss.getSheetByName(sheetName);
  
  if (!sheet) {{
    sheet = ss.insertSheet(sheetName);
  }} else {{
    sheet.clear();
  }}
  
  // Headers
  var headers = ['S.No', 'Type / Feature', 'Original URL', 'Updated / Canonical URL', 'Validation Status', 'HTTP Code', 'View', 'QA Status Android', 'Issue / Audit Remarks'];
  sheet.appendRow(headers);
  
  // Header Styling
  sheet.getRange(1, 1, 1, headers.length)
       .setBackground('#1F4E79')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setHorizontalAlignment('center');
       
  // Data Rows
  var data = {js_rows};
  
  if (data.length > 0) {{
    var range = sheet.getRange(2, 1, data.length, headers.length);
    range.setValues(data);
    
    // Status Color Coding
    for (var i = 0; i < data.length; i++) {{
      var status = data[i][4];
      var rowCell = sheet.getRange(i + 2, 5);
      if (status.indexOf('WORKING') !== -1) {{
        rowCell.setBackground('#E2EFDA').setFontColor('#375623').setFontWeight('bold');
      }} else if (status.indexOf('REDIRECTED') !== -1) {{
        rowCell.setBackground('#DDEBF7').setFontColor('#1F4E78').setFontWeight('bold');
      }} else if (status.indexOf('BROKEN') !== -1) {{
        rowCell.setBackground('#FCE4D6').setFontColor('#C65911').setFontWeight('bold');
      }}
    }}
  }}
  
  // Auto-resize columns
  for (var col = 1; col <= headers.length; col++) {{
    sheet.autoResizeColumn(col);
  }}
}}
"""

with open('output/cleaned_google_sheet/google_apps_script_runner.js', 'w', encoding='utf-8') as f:
    f.write(script_code)

print('Generated 1-Click Apps Script file: output/cleaned_google_sheet/google_apps_script_runner.js')
