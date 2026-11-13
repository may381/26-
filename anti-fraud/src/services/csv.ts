/** Prevent spreadsheet formula execution when exporting untrusted model/input text. */
export function csvCell(value:unknown):string {
  let text=String(value??'');
  if (/^[\s\uFEFF]*[=+@-]/.test(text) || /^[\t\r\n]/.test(text)) text="'"+text;
  return '"'+text.replace(/"/g,'""')+'"';
}
