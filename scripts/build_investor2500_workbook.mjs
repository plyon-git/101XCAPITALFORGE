#!/usr/bin/env node
/**
 * Create the investor campaign workbook using the Codex primary runtime.
 * Run a temporary copy with a tmp node_modules symlink to the runtime bundle.
 * Pass the repository root as the first argument. No source data is changed.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const repoRoot = path.resolve(process.argv[2] ?? path.join(path.dirname(fileURLToPath(import.meta.url)), '..'));
const previewDir = path.resolve(process.argv[3] ?? path.join(process.cwd(), 'preview'));
const records = (await fs.readFile(path.join(repoRoot, 'data/investor2500_research.jsonl'), 'utf8'))
  .split(/\r?\n/).filter(Boolean).map(line => JSON.parse(line));
const sourceSummary = JSON.parse(await fs.readFile(path.join(repoRoot, 'data/investor2500_summary.json'), 'utf8'));
if (records.length !== 2500 || sourceSummary.prospects !== 2500) throw new Error('Expected exactly 2,500 complete prospect rows.');
if (new Set(records.map(row => row.prospect_id)).size !== 2500) throw new Error('Prospect identifiers are not unique.');

const columns = [
  ['Rank', (_, index) => index + 1, 8],
  ['Company', row => row.company, 48],
  ['Named contact', row => row.name, 32],
  ['Category', row => row.category, 34],
  ['Priority', row => row.priority, 38],
  ['Status', () => 'New', 18],
  ['Email', row => row.email, 36],
  ['Phone', row => row.phone, 20],
  ['Website', row => row.website, 48],
  ['State', row => row.state, 10],
  ['City', row => row.city, 22],
  ['Contact role', row => row.contact_role, 58],
  ['Contact URL', row => row.contact_url, 70],
  ['Check status', row => row.check_status, 66],
  ['Published minimum USD', row => row.published_min, 22],
  ['Published maximum USD', row => row.published_max, 22],
  ['Range meaning', row => row.range_scope, 84],
  ['Fit', row => row.fit_reason, 84],
  ['Requirements', row => row.requirements, 96],
  ['Next action', row => row.next_action, 84],
  ['Source URLs', row => (row.source_urls ?? []).join('\n'), 96],
  ['Checked date', row => excelDate(row.checked_at), 16],
  ['Source date', row => excelDate(row.source_date), 16],
  ['Source provenance', row => row.source_provenance, 76],
  ['Email source URL', row => row.email_source_url, 76],
  ['Phone source URL', row => row.phone_source_url, 76],
  ['Evidence', row => row.evidence, 100],
  ['Discovery', row => row.discovery_origin, 62],
  ['Capital status', row => row.capital_verification, 28],
  ['Approval status', row => row.approval_status, 42],
  ['Primary activity checked', row => row.primary_activity_verified ? 'Yes' : 'No', 24],
  ['Primary contact checked', row => row.primary_contact_verified ? 'Yes' : 'No', 24],
  ['Other published contacts', row => (row.related_published_contacts ?? []).join('; '), 64],
  ['Company aliases', row => (row.company_aliases ?? []).join('; '), 84],
  ['Notes', () => null, 54],
  ['Prospect ID', row => row.prospect_id, 28],
  ['Original category', row => row.original_category, 58],
  ['Requested minimum USD', row => row.requested_min, 22],
  ['Requested maximum USD', row => row.requested_max, 22],
  ['Primary source URL', row => row.source_url, 96],
  ['Origin file', row => row.origin_file, 48],
  ['Published cash capacity USD', row => row.cash_capacity, 28],
];

function excelDate(value) {
  if (!value) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const date = new Date(`${value}T00:00:00Z`);
    if (!Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value) return date;
  }
  return value;
}

function literal(value) {
  if (value === undefined || value === null || value === '') return null;
  if (typeof value !== 'string') return value;
  if (value.length > 32767) throw new Error('A source field exceeds the Excel cell text limit.');
  return value.startsWith('=') ? `'${value}` : value;
}

function col(index) {
  let name = '';
  for (let n = index + 1; n > 0; n = Math.floor((n - 1) / 26)) name = String.fromCharCode(65 + (n - 1) % 26) + name;
  return name;
}

function write(sheet, address, value) { sheet.getRange(address).values = [[literal(value)]]; }
function formula(sheet, address, expression) { sheet.getRange(address).formulas = [[expression]]; }
function section(sheet, address, heading) {
  const area = sheet.getRange(address);
  area.format.fill = '#1D3553';
  area.format.font = { name: 'Arial', size: 10, color: '#FFFFFF', bold: true };
  area.format.rowHeight = 24;
  write(sheet, address.split(':')[0], heading);
}

const workbook = Workbook.create();
const summary = workbook.worksheets.add('Summary');
const prospects = workbook.worksheets.add('Prospects2500');
summary.showGridLines = false;
prospects.showGridLines = false;
summary.tabColor = '#1D3553';
prospects.tabColor = '#6687A3';

const lastColumn = col(columns.length - 1);
const lastRow = records.length + 1;
prospects.getRange(`A1:${lastColumn}${lastRow}`).values = [
  columns.map(([name]) => name),
  ...records.map((row, index) => columns.map(([, getter]) => literal(getter(row, index)))),
];
prospects.getRange(`A1:${lastColumn}${lastRow}`).format = {
  font: { name: 'Arial', size: 10, color: '#233248' },
  verticalAlignment: 'center',
  rowHeight: 36,
  wrapText: false,
};
columns.forEach(([, , width], index) => { prospects.getRange(`${col(index)}1:${col(index)}${lastRow}`).format.columnWidth = width; });
const table = prospects.tables.add(`A1:${lastColumn}${lastRow}`, true, 'InvestorProspects');
table.style = 'TableStyleMedium2';
table.showFilterButton = true;
table.showTotals = false;
prospects.getRange(`A1:${lastColumn}1`).format = {
  fill: '#1D3553',
  font: { name: 'Arial', size: 10, color: '#FFFFFF', bold: true },
  horizontalAlignment: 'center',
  verticalAlignment: 'center',
  wrapText: true,
  rowHeight: 32,
  borders: { insideVertical: { style: 'thin', color: '#FFFFFF' } },
};
prospects.getRange(`B2:E${lastRow}`).format.wrapText = true;
prospects.getRange(`F2:N${lastRow}`).setNumberFormat('@');
prospects.getRange(`F2:F${lastRow}`).format.fill = '#FFF6DD';
prospects.getRange(`AI2:AI${lastRow}`).format.fill = '#FFF6DD';
prospects.getRange(`F2:F${lastRow}`).dataValidation = { rule: { type: 'list', values: ['New', 'Reviewing', 'Contacted', 'Due diligence', 'Terms', 'Passed'] } };
prospects.getRange(`O2:P${lastRow}`).setNumberFormat('"$"#,##0');
prospects.getRange(`AL2:AM${lastRow}`).setNumberFormat('"$"#,##0');
prospects.getRange(`AP2:AP${lastRow}`).setNumberFormat('"$"#,##0');
prospects.getRange(`O2:P${lastRow}`).format.horizontalAlignment = 'right';
prospects.getRange(`V2:W${lastRow}`).setNumberFormat('mm/dd/yy');
prospects.getRange(`A2:A${lastRow}`).setNumberFormat('#,##0');
prospects.getRange(`A2:A${lastRow}`).format.horizontalAlignment = 'right';
prospects.getRange(`G2:I${lastRow}`).format.font = { name: 'Arial', size: 10, color: '#1F5283' };
prospects.getRange(`Q2:AA${lastRow}`).format.font = { name: 'Arial', size: 10, color: '#53657B' };
prospects.freezePanes.freezeRows(1);
prospects.freezePanes.freezeColumns(2);

summary.getRange('A1:G31').format = {
  font: { name: 'Arial', size: 10, color: '#233248' },
  rowHeight: 22,
  verticalAlignment: 'center',
  wrapText: false,
};
const summaryWidths = [42, 16, 3, 56, 16, 3, 64];
summaryWidths.forEach((width, index) => { summary.getRange(`${col(index)}1:${col(index)}31`).format.columnWidth = width; });
summary.getRange('A1:G1').format.rowHeight = 8;
write(summary, 'A2', '101XVC CapitalForge');
summary.getRange('A2').format.font = { name: 'Arial', size: 14, bold: true, color: '#1D3553' };
write(summary, 'A3', '2,500 potential investor contacts');
summary.getRange('A3').format.font = { name: 'Arial', size: 10, color: '#53657B' };
summary.getRange('A4:G4').format = { rowHeight: 8, borders: { bottom: { style: 'thin', color: '#C6D3DF' } } };
write(summary, 'G2', 'Source review date');
write(summary, 'G3', excelDate(sourceSummary.checked_at));
summary.getRange('G3').setNumberFormat('mmm d, yyyy');

section(summary, 'A5:B5', 'Contact coverage');
const metrics = [
  ['Potential investor prospects', '=COUNTA(InvestorProspects[Company])', 'prospects'],
  ['Public business emails', '=COUNTA(InvestorProspects[Email])', 'public_emails'],
  ['Public business phones', '=COUNTA(InvestorProspects[Phone])', 'public_phones'],
  ['Email and phone published', '=COUNTIFS(InvestorProspects[Email],"<>",InvestorProspects[Phone],"<>")', 'email_phone_pairs'],
  ['Published business websites', '=COUNTA(InvestorProspects[Website])', 'published_business_websites'],
  ['Newly collected prospects', '=COUNTIFS(InvestorProspects[Discovery],"New public-source collection")', 'new_source_prospects'],
  ['First-party activity checks', '=COUNTIFS(InvestorProspects[Primary activity checked],"Yes")', 'primary_operator_activity_checks'],
  ['First-party contact checks', '=COUNTIFS(InvestorProspects[Primary contact checked],"Yes")', null],
  ['Published source ranges', '=COUNTA(InvestorProspects[Published minimum USD])+COUNTA(InvestorProspects[Published maximum USD])-COUNTIFS(InvestorProspects[Published minimum USD],"<>",InvestorProspects[Published maximum USD],"<>")', null],
  ['Approved transactions', '=COUNTIFS(InvestorProspects[Approval status],"Approved")', 'confirmed_deal_approvals'],
  ['Documented available cash', '=COUNTIFS(InvestorProspects[Capital status],"verified")', 'documented_available_cash'],
];
metrics.forEach(([label, expression], index) => {
  const row = 6 + index;
  write(summary, `A${row}`, label);
  formula(summary, `B${row}`, expression);
});
summary.getRange('B6:B16').setNumberFormat('#,##0');
summary.getRange('B6:B16').format.horizontalAlignment = 'right';
summary.getRange('A6:B6').format.font = { name: 'Arial', size: 10, bold: true, color: '#233248' };
summary.getRange('A6:B16').format.borders = { bottom: { style: 'thin', color: '#D7E1EB' } };

section(summary, 'D5:E5', 'Prospecting order');
write(summary, 'E5', 'Count');
summary.getRange('E5').format.horizontalAlignment = 'center';
const priorities = Object.keys(sourceSummary.by_priority ?? {});
if (priorities.length > 10) throw new Error('The priority layout expects at most ten distinct groups.');
priorities.forEach((priority, index) => {
  const row = 6 + index;
  write(summary, `D${row}`, priority);
  formula(summary, `E${row}`, `=COUNTIFS(InvestorProspects[Priority],D${row})`);
});
summary.getRange(`E6:E${Math.max(6, priorities.length + 5)}`).setNumberFormat('#,##0');
summary.getRange(`E6:E${Math.max(6, priorities.length + 5)}`).format.horizontalAlignment = 'right';

section(summary, 'A19:B19', 'Agreement underwriting base (USD)');
summary.getRange('A20:B25').values = [
  ['Trial closed-property target', 500],
  ['Underwritten gross spread per property', 20000],
  ['101XVC assignment-fee share', 0.5],
  ['Underwritten 101XVC fee per closing', null],
  ['Gross 101XVC assignment-fee base', null],
  ["Before 101XVC's own costs", null],
];
formula(summary, 'B23', '=B21*B22');
formula(summary, 'B24', '=B20*B23');
summary.getRange('B20').setNumberFormat('#,##0');
summary.getRange('B21').setNumberFormat('"$"#,##0');
summary.getRange('B22').setNumberFormat('0%');
summary.getRange('B23:B24').setNumberFormat('"$"#,##0');
summary.getRange('B20:B24').format.horizontalAlignment = 'right';
summary.getRange('B20:B22').format.font = { name: 'Arial', size: 10, color: '#255FA3' };
summary.getRange('A24:B24').format = { fill: '#E9EFF5', font: { name: 'Arial', size: 10, bold: true, color: '#233248' }, borders: { top: { style: 'thin', color: '#8AA3BA' } } };
summary.getRange('A25').format.font = { name: 'Arial', size: 10, color: '#53657B', italic: true };
write(summary, 'A28', 'Requested operating capital');
write(summary, 'A29', 'Minimum requested');
write(summary, 'B29', 100000);
write(summary, 'A30', 'Maximum requested');
write(summary, 'B30', 500000);
summary.getRange('B29:B30').setNumberFormat('"$"#,##0');
summary.getRange('B29:B30').format.horizontalAlignment = 'right';

const notes = [
  ['G5', 'How to use this list'],
  ['G6', 'Filter Prospects2500 by category, priority and state.'],
  ['G7', 'Open the source and qualify the decision maker.'],
  ['G8', 'Record replies and follow-up tasks in CapitalForge.'],
  ['G9', 'Amber Status and Notes cells are editable outreach fields.'],
  ['G10', 'Blank contact fields were not published in checked sources.'],
  ['G11', 'A public contact does not establish investing authority.'],
  ['G12', 'Published ranges retain their stated product meaning.'],
  ['G13', 'Property-loan ranges are not corporate-investment tickets.'],
  ['G14', 'Ticket, liquidity and interest remain unconfirmed.'],
  ['G19', 'Agreement basis'],
  ['G20', '$20K gross spread x 500 properties x 50% = $5M.'],
  ['G21', 'Original §§2.14(d), 2.23 and 2.19; amendment §§1.A and 3.'],
  ['G23', 'Management sensitivity: $3.9M-$7.2M.'],
  ['G24', 'Agreement-derived underwriting base: $5M.'],
  ['G26', 'Original §5.3: each party bears its own costs.'],
];
notes.forEach(([cell, value]) => write(summary, cell, value));
for (const cell of ['G5', 'G19', 'A28']) summary.getRange(cell).format.font = { name: 'Arial', size: 10, bold: true, color: '#1D3553' };
summary.getRange('G10:G14').format.font = { name: 'Arial', size: 10, color: '#53657B' };
summary.getRange('G20:G26').format.font = { name: 'Arial', size: 10, color: '#53657B' };
workbook.notes.add({
  id: 'Summary:B20',
  target: { cell: { sheetName: summary.name, sheetId: summary.sheetId, address: 'B20' } },
  authorId: '', createdAt: '',
  body: { plainText: 'Source: supplied 101XVC Acquisition Holdings trial context and Contract 1 Amendment v2, October 2, 2026. Agreement underwriting basis: original §§2.14(d), 2.23 and 2.19; amendment §§1.A and 3. $20,000 underwritten gross spread per property x 500 trial closed-property target x 50% 101XVC assignment-fee share = $5,000,000 gross 101XVC assignment-fee base. Original §5.3: each party bears its own costs. AH acquisition costs are not netted before the split. Private agreement is not embedded.' },
});

// Check that ordinary source-cell edits update the summary, then restore them.
workbook.recalculate();
const emailIndex = records.findIndex(row => row.email);
if (emailIndex >= 0) {
  const emailCell = `G${emailIndex + 2}`;
  write(prospects, emailCell, null);
  workbook.recalculate();
  if (summary.getRange('B7').values[0][0] !== sourceSummary.public_emails - 1) throw new Error('Email coverage did not update after a temporary cell edit.');
  write(prospects, emailCell, records[emailIndex].email);
}
write(summary, 'B21', 22000);
workbook.recalculate();
if (summary.getRange('B24').values[0][0] !== 5500000) throw new Error('Agreement basis did not update after a temporary spread edit.');
write(summary, 'B21', 20000);
workbook.recalculate();
const expected = metrics.map(([label, , key], index) => [label, `B${6 + index}`, key ? sourceSummary[key] : null]);
for (const [label, address, control] of expected) {
  const result = summary.getRange(address).values[0][0];
  if (control !== null && control !== undefined && result !== control) throw new Error(`${label}: calculated ${result}, source control ${control}`);
}
for (const [address, control] of [
  ['B13', records.filter(row => row.primary_contact_verified).length],
  ['B14', records.filter(row => row.published_min !== null && row.published_min !== undefined || row.published_max !== null && row.published_max !== undefined).length],
]) {
  if (summary.getRange(address).values[0][0] !== control) throw new Error(`Independent count does not reconcile at ${address}.`);
}
priorities.forEach((priority, index) => {
  if (summary.getRange(`E${6 + index}`).values[0][0] !== sourceSummary.by_priority[priority]) throw new Error(`Priority count does not reconcile: ${priority}`);
});
if (summary.getRange('B24').values[0][0] !== 5000000) throw new Error('Agreement underwriting base does not reconcile to $5,000,000.');
const errors = await workbook.inspect({
  kind: 'match', searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',
  options: { useRegex: true, maxResults: 30 }, summary: 'Final formula error scan', maxChars: 2500,
});
console.log(errors.ndjson);
const inspection = await workbook.inspect({ kind: 'table', range: 'Summary!A5:E16', include: 'values,formulas', tableMaxRows: 12, tableMaxCols: 5, maxChars: 5000 });
console.log(inspection.ndjson);
const detailInspection = await workbook.inspect({ kind: 'table', range: 'Prospects2500!A2497:J2501', include: 'values', tableMaxRows: 5, tableMaxCols: 10, tableMaxCellChars: 60, maxChars: 2500 });
console.log(detailInspection.ndjson);

await fs.mkdir(previewDir, { recursive: true });
for (const [sheetName, range, name] of [
  ['Summary', 'A1:G31', 'investor2500_summary.png'],
  ['Prospects2500', 'A1:I10', 'investor2500_prospects.png'],
]) {
  const preview = await workbook.render({ sheetName, range, scale: 1.5, format: 'png' });
  await fs.writeFile(path.join(previewDir, name), new Uint8Array(await preview.arrayBuffer()));
}
const outputPath = path.join(repoRoot, 'downloads/CapitalForge_2500_Potential_Investors.xlsx');
await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
// Keep artifact export diagnostics with the previews rather than in the Git deliverable folder.
await fs.rename(`${outputPath}.inspect.ndjson`, path.join(previewDir, 'artifact_export.inspect.ndjson')).catch(error => {
  if (error.code !== 'ENOENT') throw error;
});
await fs.writeFile(path.join(previewDir, 'workbook_verification.json'), JSON.stringify({
  rows: records.length, columns: columns.length, summary_controls: expected,
  table_range: `A1:${lastColumn}${lastRow}`, frozen_rows: 1, frozen_columns: 2,
  gross_101xvc_assignment_fee_base: summary.getRange('B24').values[0][0], output: outputPath,
}, null, 2));
console.log(JSON.stringify({ output: outputPath, rows: records.length, columns: columns.length, previews: previewDir }));
