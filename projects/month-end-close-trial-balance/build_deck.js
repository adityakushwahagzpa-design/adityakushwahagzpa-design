const pptxgen = require("pptxgenjs");
const { applyTheme } = require("/root/.claude/skills/synced/05fee941-b802-442c-a8a8-2b6d3fa13250_b3925eac-ab9e-4700-9671-c0c8f8fd382b/pptx/scripts/apply_theme.js");
const D = require("/home/claude/deck_data.json");

const THEME = { name: "Close Pack", headFontFace: "Cambria", bodyFontFace: "Calibri",
  colors: { dk1: "1B2433", lt1: "FFFFFF", dk2: "0E3B43", lt2: "EEF3F4", accent1: "0F766E", accent2: "C2410C",
            accent3: "64748B", accent4: "15803D", accent5: "B45309", accent6: "334155", hlink: "0F766E", folHlink: "334155" } };
const HEX = { teal: "0F766E", orange: "C2410C", grid: "D9E2E5", slate: "64748B" };
const inr = n => { const neg = n < 0; n = Math.round(Math.abs(n)); let s = String(n); if (s.length > 3) { const last = s.slice(-3); let rest = s.slice(0, -3); rest = rest.replace(/\B(?=(\d{2})+(?!\d))/g, ","); s = rest + "," + last; } return (neg ? "(" : "") + s + (neg ? ")" : ""); };
const lakh = n => "₹" + (n / 1e5).toFixed(2) + " lakh";

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9"; // 10 x 5.625
  pres.author = "Aditya Kushwaha"; pres.title = "October 2026 Month-End Close Pack";
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  const C = pres.SchemeColor;

  pres.defineSlideMaster({ title: "TITLE_DARK", background: { color: C.text2 },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.55, w: 8.8, h: 1.3, fontSize: 40, bold: true, color: C.background1, valign: "bottom" }, text: "" } },
      { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 3.0, w: 8.8, h: 1.2, fontSize: 16, color: "CFE3E1", valign: "top" }, text: "" } },
      { text: { text: "Sample data for a fictional company · portfolio project", options: { x: 0.6, y: 5.0, w: 8.8, h: 0.3, fontSize: 10, color: "9FC3C0" } } } ] });
  pres.defineSlideMaster({ title: "CONTENT", background: { color: C.background1 },
    margin: [0.5, 0.5, 0.6, 0.5],
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9.0, h: 0.85, fontSize: 24, bold: true, color: C.text2, valign: "top" }, text: "" } },
      { text: { text: "Kaveri Home Appliances Pvt. Ltd. · October 2026 close · sample data", options: { x: 0.5, y: 5.2, w: 7.5, h: 0.25, fontSize: 10, color: C.accent3 } } } ],
    slideNumber: { x: 9.0, y: 5.2, w: 0.5, h: 0.25, fontSize: 10, color: "64748B", align: "right" } });
  pres.defineSlideMaster({ title: "CLOSING_DARK", background: { color: C.text2 },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9.0, h: 0.85, fontSize: 24, bold: true, color: C.background1, valign: "top" }, text: "" } },
      { text: { text: "Kaveri Home Appliances Pvt. Ltd. · October 2026 close · sample data", options: { x: 0.5, y: 5.2, w: 7.5, h: 0.25, fontSize: 10, color: "9FC3C0" } } } ],
    slideNumber: { x: 9.0, y: 5.2, w: 0.5, h: 0.25, fontSize: 10, color: "9FC3C0", align: "right" } });

  const card = (s, x, y, w, h, name, fill) => s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: fill || C.background2 }, line: { color: fill || C.background2 }, objectName: name });

  // 1 Title
  pres.addSection({ title: "Opening" });
  let s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Opening" });
  s.addText("October 2026 Month-End Close", { placeholder: "title" });
  s.addText("Close pack for the Finance Controller · Kaveri Home Appliances Pvt. Ltd.\nPrepared by Aditya Kushwaha", { placeholder: "body" });
  s.addNotes("Close pack for October 2026. Sample data for a fictional consumer durables distributor. The workbook behind every number is in the GitHub project month-end-close-trial-balance.");

  // 2 Executive summary
  pres.addSection({ title: "Summary" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Summary" });
  s.addText("Books closed on working day 5 with every check passing; month-end entries cut profit by half", { placeholder: "title" });
  const stats = [["₹23.40 lakh", "Revenue, 30 invoices"], ["₹2.27 lakh", "Net profit, 9.7% margin"], ["₹2.14 lakh", "9 adjusting entries"], ["3 of 3", "Reconciliations at ₹0 difference"]];
  stats.forEach(([v, l], i) => { const x = 0.5 + i * 2.3; card(s, x, 1.45, 2.1, 1.65, "stat" + i);
    s.addText(v, { x: x + 0.15, y: 1.6, w: 1.8, h: 0.75, fontSize: 21, bold: true, color: C.accent1, fontFace: "Cambria", isTextBox: true, margin: 0, valign: "middle" });
    s.addText(l, { x: x + 0.15, y: 2.4, w: 1.8, h: 0.55, fontSize: 13, color: C.text1, isTextBox: true, margin: 0, valign: "top" }); });
  s.addText([{ text: "Profit before month-end entries ", options: {} }, { text: "₹4.41 lakh", options: { bold: true } }, { text: "  →  after ", options: {} }, { text: "₹2.27 lakh", options: { bold: true, color: C.accent2 } },
    { text: "  ·  Trial balance agrees at ₹91,75,750 on each side  ·  Balance sheet balances at ₹63,48,300", options: {} }],
    { x: 0.5, y: 3.45, w: 9.0, h: 0.5, fontSize: 14, color: C.text1, isTextBox: true, margin: 0 });
  s.addText("Three items need follow-up in November: an unpresented supplier cheque of ₹6,80,000, a ₹7,500 inventory count shortfall and ₹45,000 of contract wages paid after month end.",
    { x: 0.5, y: 4.1, w: 9.0, h: 0.7, fontSize: 14, color: C.accent3, isTextBox: true, margin: 0 });
  s.addNotes("Headline: the close finished on schedule and all controls passed. The 9 adjusting entries worth 2.14 lakh take profit from 4.41 to 2.27 lakh. Three follow-ups carry into November.");

  // 3 Timeline
  pres.addSection({ title: "Close process" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Close process" });
  s.addText("A five-day close: cut-off and bank first, accruals and counts next, sign-off last", { placeholder: "title" });
  const days = [["WD-1", ["Sales and purchase cut-off", "Bank reconciliation"], "AR / AP team, R2R"],
    ["WD-2", ["Accruals and interest", "Insurance prepayment", "Depreciation run"], "R2R analyst"],
    ["WD-3", ["Inventory count posted", "Allowance review", "Subledger to GL"], "R2R, warehouse"],
    ["WD-4", ["Adjusted trial balance", "Balance sheet review"], "R2R, controller"],
    ["WD-5", ["P&L and balance sheet issued", "Period locked"], "Finance controller"]];
  s.addShape(pres.shapes.LINE, { x: 1.33, y: 1.75, w: 7.28, h: 0, line: { color: C.accent3, width: 1.5 }, objectName: "timeline" });
  days.forEach(([d, tasks, owner], i) => { const x = 0.5 + i * 1.82;
    s.addShape(pres.shapes.OVAL, { x: x + 0.53, y: 1.45, w: 0.6, h: 0.6, fill: { color: C.accent1 }, line: { color: C.background1, width: 2 }, objectName: "day" + i });
    s.addText(String(i + 1), { x: x + 0.53, y: 1.45, w: 0.6, h: 0.6, fontSize: 16, bold: true, color: C.background1, align: "center", valign: "middle", isTextBox: true, margin: 0 });
    s.addText(d, { x, y: 2.15, w: 1.66, h: 0.3, fontSize: 14, bold: true, color: C.text2, align: "center", isTextBox: true, margin: 0 });
    card(s, x, 2.55, 1.66, 2.3, "tasks" + i);
    s.addText(tasks.map((t, k) => ({ text: t, options: { bullet: { indent: 10 }, breakLine: k < tasks.length - 1 } })), { x: x + 0.08, y: 2.65, w: 1.52, h: 1.6, fontSize: 12, color: C.text1, valign: "top", paraSpaceAfter: 4, isTextBox: true, margin: 0 });
    s.addText(owner, { x: x + 0.08, y: 4.35, w: 1.52, h: 0.4, fontSize: 10, italic: true, color: C.accent3, valign: "bottom", isTextBox: true, margin: 0 }); });
  s.addNotes("Twelve checklist tasks over five working days, each with an owner. Cut-off and the bank reconciliation come first so later entries start from clean cash.");

  // 4 Adjustments chart
  pres.addSection({ title: "Results" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
  s.addText("Nine adjusting entries take profit from ₹4.41 lakh to ₹2.27 lakh; accruals are over half", { placeholder: "title" });
  const short = { "ADJ-01": "Electricity accrual", "ADJ-02": "Audit fee accrual", "ADJ-03": "Contract wages accrual", "ADJ-04": "Insurance prepayment", "ADJ-05": "Depreciation",
    "ADJ-06": "Interest accrual", "ADJ-07": "Bad debt allowance", "ADJ-08": "Inventory shortfall", "ADJ-09": "Bank charges" };
  const adj = [...D.adj].sort((a, b) => a[2] - b[2]);
  s.addChart(pres.charts.BAR, [{ name: "₹ thousand", labels: adj.map(a => short[a[0]]), values: adj.map(a => a[2] / 1000) }], {
    x: 0.5, y: 1.25, w: 5.6, h: 3.85, barDir: "bar", chartColors: [HEX.orange], showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0",
    dataLabelFontSize: 11, dataLabelColor: "1B2433", dataLabelFontFace: "+mn-lt", catAxisLabelFontSize: 11, catAxisLabelFontFace: "+mn-lt", catAxisLabelColor: "1B2433",
    valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false, showTitle: true, title: "Profit impact by entry (₹ thousand)", titleFontSize: 12, titleColor: "334155", titleFontFace: "+mn-lt", barGapWidthPct: 45 });
  const groups = [["53.5%", "Accruals", "₹1,14,750: wages, electricity, audit fee, interest"], ["37.3%", "Prepayment and depreciation", "₹80,000: insurance release and equipment depreciation"], ["9.2%", "Valuation and bank", "₹19,700: allowance, inventory count, bank charges"]];
  groups.forEach(([p, h, d], i) => { const y = 1.35 + i * 1.25; card(s, 6.4, y, 3.1, 1.1, "group" + i);
    s.addText(p, { x: 6.55, y: y + 0.1, w: 1.0, h: 0.5, fontSize: 22, bold: true, color: C.accent1, fontFace: "Cambria", isTextBox: true, margin: 0 });
    s.addText(h, { x: 7.55, y: y + 0.12, w: 1.9, h: 0.45, fontSize: 13, bold: true, color: C.text1, isTextBox: true, margin: 0, valign: "middle" });
    s.addText(d, { x: 6.55, y: y + 0.6, w: 2.85, h: 0.45, fontSize: 11, color: C.accent3, isTextBox: true, margin: 0 }); });
  s.addNotes("Total adjustments 2,14,450 rupees. Accruals are 53.5 percent, prepayment release and depreciation 37.3 percent, valuation and bank items 9.2 percent.");

  // 5 P&L
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
  s.addText("Gross margin holds at 39.7%; the fall in profit comes from costs booked at month end", { placeholder: "title" });
  const P = Object.fromEntries(D.pl.map(r => [r[0], [r[1], r[2]]]));
  const grp = (names) => names.reduce((a, n) => [a[0] + P[n][0], a[1] + P[n][1]], [0, 0]);
  const rows = [["Sales revenue", P["Sales Revenue"]], ["Cost of goods sold", P["Cost of Goods Sold"].map(v => -v)]];
  const gpU = P["Sales Revenue"][0] - P["Cost of Goods Sold"][0], gpA = P["Sales Revenue"][1] - P["Cost of Goods Sold"][1];
  const op = [["Salaries and wages", P["Salaries and Wages"]], ["Rent", P["Rent"]], ["Marketing", P["Marketing"]], ["Electricity, audit fee and interest", grp(["Electricity", "Audit Fees", "Interest Expense"])],
    ["Insurance and depreciation", grp(["Insurance", "Depreciation"])], ["Bad debts and bank charges", grp(["Bad Debt Expense", "Bank Charges"])]];
  const totU = op.reduce((a, r) => a + r[1][0], 0), totA = op.reduce((a, r) => a + r[1][1], 0);
  const hdr = ["", "Before adjustments (₹)", "Adjustments (₹)", "After adjustments (₹)"].map((t, i) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: "0E3B43" }, align: i ? "right" : "left" } }));
  const r3 = (label, u, a, opt = {}) => [{ text: label, options: { bold: !!opt.bold } }, { text: u ? inr(u) : "–", options: { align: "right", bold: !!opt.bold, color: u ? "1B2433" : "64748B" } }, { text: a - u ? inr(a - u) : "–", options: { align: "right", color: a - u ? "C2410C" : "64748B", bold: !!opt.bold } }, { text: inr(a), options: { align: "right", bold: !!opt.bold } }];
  const body = [r3("Sales revenue", rows[0][1][0], rows[0][1][1]), r3("Cost of goods sold", rows[1][1][0], rows[1][1][1]), r3("Gross profit", gpU, gpA, { bold: true }),
    ...op.map(r => r3(r[0], -r[1][0], -r[1][1])), r3("Net profit", gpU - totU, gpA - totA, { bold: true })];
  s.addTable([hdr, ...body], { x: 0.5, y: 1.3, w: 9.0, colW: [3.6, 1.8, 1.8, 1.8], fontSize: 12, fontFace: "Calibri", color: "1B2433", rowH: 0.3,
    border: { type: "solid", pt: 0.5, color: "D9E2E5" }, fill: { color: "FFFFFF" } });
  s.addNotes("Revenue is unchanged by the close. Cost of goods sold rises by 7,500 for the inventory shortfall. The other 2,06,950 of adjustments are operating costs booked at month end.");

  // 6 Balance sheet
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
  s.addText("The balance sheet balances at ₹63,48,300; cash and receivables make up nearly half of assets", { placeholder: "title" });
  const B = D.bs;
  const assets = [["Cash at bank", B["Cash at Bank"]], ["Receivables, net of allowance", B["Accounts Receivable"] + B["Allowance for Doubtful Debts"]], ["Inventory", B["Inventory"]], ["Prepaid insurance", B["Prepaid Insurance"]], ["Equipment, net of depreciation", B["Office Equipment"] + B["Accumulated Depreciation"]]];
  const liabs = [["Accounts payable", -B["Accounts Payable"]], ["Accruals, wages and interest payable", -(B["Accrued Expenses"] + B["Salaries Payable"] + B["Interest Payable"])], ["Term loan", -B["Term Loan"]], ["Share capital", -B["Share Capital"]], ["Retained earnings incl. October profit", -B["Retained Earnings"] + D.facts.net_profit]];
  const tA = assets.reduce((a, r) => a + r[1], 0), tL = liabs.reduce((a, r) => a + r[1], 0);
  const btab = (title, items, tot) => [[{ text: title, options: { bold: true, color: "FFFFFF", fill: { color: "0E3B43" } } }, { text: "₹", options: { bold: true, color: "FFFFFF", fill: { color: "0E3B43" }, align: "right" } }],
    ...items.map(r => [{ text: r[0] }, { text: inr(r[1]), options: { align: "right" } }]), [{ text: "Total", options: { bold: true } }, { text: inr(tot), options: { bold: true, align: "right" } }]];
  const tOpt = (x) => ({ x, y: 1.3, w: 4.35, colW: [3.0, 1.35], fontSize: 12, fontFace: "Calibri", color: "1B2433", rowH: 0.36, border: { type: "solid", pt: 0.5, color: "D9E2E5" }, fill: { color: "FFFFFF" } });
  s.addTable(btab("Assets", assets, tA), tOpt(0.5)); s.addTable(btab("Liabilities and equity", liabs, tL), tOpt(5.15));
  card(s, 0.5, 4.05, 9.0, 0.75, "check", "E3F1EE");
  s.addText(`Check: assets ${inr(tA)} minus liabilities and equity ${inr(tL)} = ${inr(tA - tL)}. Trial balance debits and credits agree at ₹91,75,750.`, { x: 0.7, y: 4.1, w: 8.6, h: 0.65, fontSize: 14, color: C.accent1, bold: true, valign: "middle", isTextBox: true, margin: 0 });
  s.addNotes("Every line links to the adjusted trial balance. October profit of 2,26,550 is added to opening retained earnings of 13,37,000.");

  // 7 Reconciliations
  pres.addSection({ title: "Controls" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Controls" });
  s.addText("All three reconciliations close at zero; the only bank difference is one supplier cheque in transit", { placeholder: "title" });
  const ar = D.ar.reduce((a, x) => a + x[1], 0), ap = D.ap.reduce((a, x) => a + x[1], 0);
  const recs = [["Bank", [["Bank statement", D.bank.stmt], ["Less cheque 004512 in transit", -D.bank.unpresented[0][1]], ["Adjusted bank balance", D.bank.stmt - D.bank.unpresented[0][1]], ["General ledger cash", D.bank.gl]]],
    ["Receivables", [...D.ar.map(x => [x[0], x[1]]), ["Subledger total", ar], ["GL control account 1100", ar]]],
    ["Payables", [...D.ap.map(x => [x[0], x[1]]), ["Subledger total", ap], ["GL control account 2000", ap]]]];
  recs.forEach(([t, lines], i) => { const x = 0.5 + i * 3.05; card(s, x, 1.3, 2.85, 3.55, "rec" + i);
    s.addText(t, { x: x + 0.15, y: 1.4, w: 2.55, h: 0.4, fontSize: 16, bold: true, color: C.text2, fontFace: "Cambria", isTextBox: true, margin: 0 });
    s.addTable(lines.map((l, k) => [{ text: l[0], options: { bold: k >= lines.length - 2 } }, { text: inr(l[1]), options: { align: "right", bold: k >= lines.length - 2 } }]),
      { x: x + 0.1, y: 1.85, w: 2.65, colW: [1.75, 0.9], fontSize: 11, fontFace: "Calibri", color: "1B2433", rowH: 0.3, margin: [2, 4, 2, 4], border: { type: "none" } });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 0.15, y: 4.25, w: 2.55, h: 0.45, rectRadius: 0.06, fill: { color: C.accent4 }, line: { color: C.accent4 }, objectName: "ok" + i });
    s.addText("Difference ₹0", { x: x + 0.15, y: 4.25, w: 2.55, h: 0.45, fontSize: 13, bold: true, color: C.background1, align: "center", valign: "middle", isTextBox: true, margin: 0 }); });
  s.addNotes("Bank: statement 23,23,800 less cheque 004512 of 6,80,000 still in transit equals GL cash of 16,43,800, after posting 1,200 of bank charges. Receivables and payables subledgers agree with their control accounts.");

  // 8 Follow-ups
  pres.addSection({ title: "Next steps" });
  s = pres.addSlide({ masterName: "CLOSING_DARK", sectionTitle: "Next steps" });
  s.addText("Four follow-ups for November keep the next close faster and cleaner", { placeholder: "title" });
  const acts = [["₹6,80,000", "Cheque 004512 in transit", "Confirm it clears in the November bank statement; chase the supplier if not presented by WD-3."],
    ["₹45,000", "Contract wages after month end", "Move the contract staff payroll cut-off to the last working day so wages need no accrual."],
    ["₹7,500", "Inventory count shortfall", "Cycle-count high-value lines weekly instead of a single month-end count."],
    ["₹11,000", "Allowance top-up", "Review receivables ageing monthly; the allowance now covers 5% of ₹14.80 lakh."]];
  acts.forEach(([v, h, d], i) => { const x = 0.5 + (i % 2) * 4.6, y = 1.3 + Math.floor(i / 2) * 1.85;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 4.4, h: 1.65, rectRadius: 0.08, fill: { color: "16505A" }, line: { color: "16505A" }, objectName: "act" + i });
    s.addText(v, { x: x + 0.2, y: y + 0.12, w: 1.6, h: 0.5, fontSize: 22, bold: true, color: "F2B880", fontFace: "Cambria", isTextBox: true, margin: 0 });
    s.addText(h, { x: x + 1.85, y: y + 0.12, w: 2.4, h: 0.5, fontSize: 14, bold: true, color: C.background1, valign: "middle", isTextBox: true, margin: 0 });
    s.addText(d, { x: x + 0.2, y: y + 0.7, w: 4.0, h: 0.85, fontSize: 13, color: "D6E7E5", valign: "top", isTextBox: true, margin: 0 }); });
  s.addNotes("These are recommendations drawn from the October close, not completed actions.");

  await pres.writeFile({ fileName: "/home/claude/deck/Month_End_Close_Pack_October_2026.pptx" });
  await applyTheme("/home/claude/deck/Month_End_Close_Pack_October_2026.pptx", THEME);
  console.log("written");
})();
