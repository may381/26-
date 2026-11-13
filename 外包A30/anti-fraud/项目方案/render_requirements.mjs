import { Workbook, SpreadsheetFile } from "file:///C:/Users/dev/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";
const wb=await SpreadsheetFile.importXlsx("D:/Desktop/外包A30/anti-fraud/项目方案/详细需求分析.xlsx");
for (const name of ["需求总览","接口清单","验收标准","版本规划","风险与边界"]) { const img=await wb.render({sheetName:name,autoCrop:"all",scale:1,format:"png"}); await img.save(`D:/Desktop/外包A30/anti-fraud/项目方案/${name}.png`); }
await wb.recalculate(); console.log("rendered");
