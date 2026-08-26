// Reads report data as JSON (see report/analysis.py -> to_json_dict) and
// writes a formatted .docx. Usage: node build_docx.js data.json output.docx
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
} = require("docx");

const [, , dataPath, outPath] = process.argv;
const data = JSON.parse(fs.readFileSync(dataPath, "utf-8"));

const ALERT_COLOR = { warning: "B8860B", crisis: "C0392B" };

function heading(text, level = HeadingLevel.HEADING_1) {
  return new Paragraph({ text, heading: level, spacing: { before: 300, after: 150 } });
}

function bodyText(text, opts = {}) {
  return new Paragraph({ children: [new TextRun({ text, ...opts })], spacing: { after: 120 } });
}

function metricsTable(rows) {
  const colWidths = [4500, 4500];
  return new Table({
    width: { size: colWidths[0] + colWidths[1], type: WidthType.DXA },
    columnWidths: colWidths,
    rows: rows.map(([label, value], i) =>
      new TableRow({
        children: [
          new TableCell({
            width: { size: colWidths[0], type: WidthType.DXA },
            shading: i === 0 ? { type: ShadingType.CLEAR, fill: "F2F2F2" } : undefined,
            children: [new Paragraph({ children: [new TextRun({ text: label, bold: true })] })],
          }),
          new TableCell({
            width: { size: colWidths[1], type: WidthType.DXA },
            children: [new Paragraph(String(value))],
          }),
        ],
      })
    ),
  });
}

function mentionBlock(m) {
  const stars = m.rating ? `${"★".repeat(Math.round(m.rating))}${"☆".repeat(5 - Math.round(m.rating))}` : "";
  return [
    new Paragraph({
      children: [
        new TextRun({ text: `[${m.platform}] `, bold: true }),
        new TextRun({ text: stars, color: "B8860B" }),
      ],
      spacing: { before: 100 },
    }),
    new Paragraph({
      children: [new TextRun({ text: `"${m.text}"`, italics: true })],
      spacing: { after: 150 },
    }),
  ];
}

const children = [
  new Paragraph({
    children: [new TextRun({ text: `Reputation Report — ${data.restaurant_name}`, bold: true, size: 36 })],
    spacing: { after: 100 },
  }),
  bodyText(`${data.city}, ${data.country}  •  Generated ${data.generated_at}`, { color: "666666", size: 20 }),

  heading("Overview"),
  metricsTable([
    ["Total mentions", data.total_mentions],
    ["Positive", `${data.positive_pct}%`],
    ["Negative", `${data.negative_pct}%`],
    ["Neutral", `${data.neutral_pct}%`],
    ["Sources collected", data.sources_ok.join(", ") || "—"],
    ["Sources failed", data.sources_failed.join(", ") || "none"],
  ]),
];

if (data.alerts.length) {
  children.push(heading("Alerts"));
  for (const alert of data.alerts) {
    children.push(
      new Paragraph({
        children: [
          new TextRun({ text: alert.level === "crisis" ? "⚠ CRISIS: " : "⚠ Warning: ", bold: true, color: ALERT_COLOR[alert.level] }),
          new TextRun({ text: alert.message }),
        ],
        spacing: { after: 120 },
      })
    );
  }
}

if (Object.keys(data.platform_breakdown).length) {
  children.push(heading("Platform breakdown"));
  children.push(metricsTable(Object.entries(data.platform_breakdown)));
}

if (data.top_positive.length) {
  children.push(heading("Top positive mentions"));
  for (const m of data.top_positive) children.push(...mentionBlock(m));
}

if (data.top_negative.length) {
  children.push(heading("Mentions needing attention"));
  for (const m of data.top_negative) children.push(...mentionBlock(m));
}

// Competitors section always renders last, after every reputation section
// above — auto-discovered enrichment, not the primary deliverable. See
// report/analysis.py's build_report() for why it's ordered this way.
if (data.competitors && data.competitors.length) {
  children.push(heading("Nearby competitors (auto-detected)"));
  const rows = [["You", data.own_avg_rating != null ? String(data.own_avg_rating) : "n/a"]];
  for (const c of data.competitors) {
    rows.push([c.name, c.rating != null ? String(c.rating) : "rating not found"]);
  }
  children.push(metricsTable(rows));
  children.push(bodyText(
    "Found automatically based on your city — not a claim these are your closest or only competitors.",
    { italics: true, color: "888888", size: 18 }
  ));
}

const doc = new Document({
  sections: [{ properties: { page: { size: { width: 12240, height: 15840 } } }, children }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(outPath, buf);
  console.log(`Wrote ${outPath}`);
});
