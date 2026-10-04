// Confere o dicionário da interface: as duas línguas têm as mesmas chaves e as
// mesmas variáveis, e toda chave usada no código existe. Uso: node check_ui.js index.html
const fs = require("fs");
const html = fs.readFileSync(process.argv[2], "utf8");
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
if (scripts.length !== 1) throw new Error(`esperava um <script>, achei ${scripts.length}`);
const src = scripts[0];
new Function(src); // erro de sintaxe estoura aqui
const [, rest] = src.split("/* i18n:start */");
const [block, code] = rest.split("/* i18n:end */");
const I18N = new Function(block + "; return I18N;")();
const langs = Object.keys(I18N), base = I18N["pt-BR"], problems = [];
const vars = v => [...[].concat(v).join(" ").matchAll(/\{(\w+)\}/g)].map(m => m[1]).sort().join(",");
for (const lang of langs) {
  for (const key of Object.keys(base)) {
    if (!(key in I18N[lang])) problems.push(`${lang}: falta ${key}`);
    else if (Array.isArray(base[key]) !== Array.isArray(I18N[lang][key])) problems.push(`${lang}: ${key} singular/plural`);
    else if ([...new Set(vars(base[key]).split(","))].join() !== [...new Set(vars(I18N[lang][key]).split(","))].join())
      problems.push(`${lang}: ${key} com variáveis diferentes`);
  }
  for (const key of Object.keys(I18N[lang])) if (!(key in base)) problems.push(`${lang}: ${key} sobrando`);
}
const used = new Set([...code.matchAll(/\bt\("([\w.]+)"[,)]/g), ...code.matchAll(/\btn\([^,]+, "([\w.]+)"[,)]/g),
  ...html.matchAll(/data-i18n(?:-aria)?="([\w.]+)"/g)].map(m => m[1]));
for (const m of code.matchAll(/\b(?:num|tog|txt|pick)\("([\w.]+)"/g)) used.add("s_" + m[1]);
for (const key of used) if (!(key in base)) problems.push(`chave usada sem tradução: ${key}`);
if (problems.length) { console.error(problems.join("\n")); process.exit(1); }
console.log(`${Object.keys(base).length} chaves, ${langs.length} idiomas, ${used.size} usadas`);
