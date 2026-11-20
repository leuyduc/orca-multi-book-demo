import { Workbook } from '@oai/artifact-tool';
const workbook = Workbook.create();
workbook.worksheets.add('Demo');
console.log(workbook.help('worksheet.sort', {include:'index,examples,notes',maxChars:4000}).ndjson);
