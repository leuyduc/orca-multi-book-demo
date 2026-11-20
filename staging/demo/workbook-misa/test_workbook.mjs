import fs from 'node:fs/promises';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';

const dir = new URL('.', import.meta.url);
const input = new URL('BAN_SAO_GIA.xlsx', dir);
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(input.pathname.replace(/^\/(\w:)/, '$1')));
const sheet = workbook.worksheets.add('TEST_SORT_GIA');
sheet.getRange('A1:F4').values = [
  ['RECORD_ID','NGAY_GIA','TIEN_GIA','PHI_GIA','THAM_CHIEU_GIA','TONG_GIA'],
  ['DEMO-R-3','2026-11-03',200,2,'SYNTHETIC:3',null],
  ['DEMO-R-1','2026-11-01',50,1,'SYNTHETIC:1',null],
  ['DEMO-R-2','2026-11-02',100,3,'SYNTHETIC:2',null],
];
sheet.getRange('F2:F4').formulas = [['=C2+D2'],['=C3+D3'],['=C4+D4']];
sheet.getRange('H1').values = [['SORT_THEO_NGAY_GIA']];
sheet.getRange('H2').formulas = [['=SORT(A2:F4,2,1)']];
sheet.getRange('O1').values = [['FILTER_TIEN_TU_100']];
sheet.getRange('O2').formulas = [['=FILTER(A2:F4,C2:C4>=100)']];
sheet.getRange('A1:T6').format.columnWidth = 18;
sheet.getRange('A1:F1').format.font = {bold:true};
workbook.recalculate();
const source = sheet.getRange('A2:F4').values;
const sorted = sheet.getRange('H2:M4').values;
const filtered = sheet.getRange('O2:T3').values;
const formulas = sheet.getRange('F2:F4').formulas;
const result = {
  source, sorted, filtered, formulas,
  arithmetic_ok: source[0][5] === 202 && source[1][5] === 51 && source[2][5] === 103,
  sorted_ok: sorted.map(r => r[0]).join(',') === 'DEMO-R-1,DEMO-R-2,DEMO-R-3' && sorted[0][4] === 'SYNTHETIC:1' && sorted[1][5] === 103 && sorted[2][5] === 202,
  filtered_ok: filtered.map(r => r[0]).join(',') === 'DEMO-R-3,DEMO-R-2' && filtered[0][4] === 'SYNTHETIC:3' && filtered[1][5] === 103,
};
sheet.getRange('C3').values = [[150]];
workbook.recalculate();
const changedFiltered = sheet.getRange('O2:T4').values;
result.recalculate_ok = sheet.getRange('F3').values[0][0] === 151 &&
  changedFiltered.map(r => r[0]).join(',') === 'DEMO-R-3,DEMO-R-1,DEMO-R-2';
sheet.getRange('C3').values = [[50]];
workbook.recalculate();
const out = await SpreadsheetFile.exportXlsx(workbook);
await out.save(new URL('KET_QUA_WORKBOOK_GIA.xlsx',dir).pathname.replace(/^\/(\w:)/, '$1'));
try {
  const preview = await workbook.render({sheetName:'TEST_SORT_GIA',range:'A1:T6',format:'png'});
  await fs.writeFile(new URL('WORKBOOK_GIA.png',dir), new Uint8Array(await preview.arrayBuffer()));
  result.render_ok = true;
} catch(e) { result.render_ok = false; result.render_error = String(e); }
await fs.writeFile(new URL('ket_qua_workbook.json',dir), JSON.stringify(result,null,2));
console.log(JSON.stringify(result));
if (!result.arithmetic_ok || !result.sorted_ok || !result.filtered_ok || !result.recalculate_ok) process.exitCode = 2;
