/**
 * Google Apps Script untuk menghubungkan Google Sheets dengan GitHub Actions.
 *
 * CARA PAKAI:
 * 1. Buat Google Sheet baru, beri nama sheet pertama: "Produk" (atau biarkan sheet aktif pertama).
 * 2. Isi baris 1 (Header) kolom A sampai H persis seperti ini:
 *    Produk | Keunggulan | Link_Produk | Image_URL | Aktif | Total_Post | Terakhir_Post | Catatan_Angle
 * 3. Buka menu: Extensions -> Apps Script.
 * 4. Hapus semua kode bawaan, paste seluruh kode ini.
 * 5. Ganti nilai SECRET_KEY di bawah dengan kata sandi acak buatanmu sendiri.
 * 6. Klik Deploy -> New deployment -> pilih jenis "Web app".
 *    - Execute as: Me
 *    - Who has access: Anyone
 * 7. Klik Deploy -> Izinkan akses (Advance -> Go to ...).
 * 8. Salin Web App URL dan simpan ke GitHub Secrets sebagai SHEET_WEBHOOK_URL.
 */

const SECRET_KEY = "GANTI_DENGAN_RAHASIA_KAMU_123";
const SHEET_NAME = "Produk"; // Pastikan nama tab di bawah Google Sheet adalah "Produk"

function getTargetSheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  return ss.getSheetByName(SHEET_NAME) || ss.getSheets()[0];
}

function jsonResponse_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function doGet(e) {
  const key = (e && e.parameter && e.parameter.key) || "";
  if (key !== SECRET_KEY) {
    return jsonResponse_({ ok: false, error: "Unauthorized" });
  }

  const sheet = getTargetSheet_();
  const data = sheet.getDataRange().getValues();
  if (data.length < 2) {
    return jsonResponse_({ ok: true, items: [] });
  }

  const headers = data[0].map(h => String(h).trim());
  const items = [];

  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    const obj = { row_number: i + 1 };
    headers.forEach((h, idx) => {
      obj[h] = row[idx];
    });
    if (String(obj.Produk || "").trim() !== "") {
      items.push(obj);
    }
  }

  return jsonResponse_({ ok: true, items: items });
}

function doPost(e) {
  let body = {};
  try {
    body = JSON.parse((e && e.postData && e.postData.contents) || "{}");
  } catch (err) {
    return jsonResponse_({ ok: false, error: "Invalid JSON body" });
  }

  if (body.key !== SECRET_KEY) {
    return jsonResponse_({ ok: false, error: "Unauthorized" });
  }

  const rowNumber = Number(body.row_number);
  if (!rowNumber || rowNumber < 2) {
    return jsonResponse_({ ok: false, error: "Invalid row_number" });
  }

  const sheet = getTargetSheet_();
  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0].map(h => String(h).trim());

  const colIndex = (name) => headers.indexOf(name) + 1;
  const totalCol = colIndex("Total_Post");
  const lastCol = colIndex("Terakhir_Post");
  const angleCol = colIndex("Catatan_Angle");

  if (totalCol > 0) {
    const current = Number(sheet.getRange(rowNumber, totalCol).getValue()) || 0;
    sheet.getRange(rowNumber, totalCol).setValue(current + 1);
  }
  if (lastCol > 0) {
    sheet.getRange(rowNumber, lastCol).setValue(body.terakhir_post || new Date().toISOString());
  }
  if (angleCol > 0 && body.catatan_angle) {
    sheet.getRange(rowNumber, angleCol).setValue(String(body.catatan_angle));
  }

  return jsonResponse_({ ok: true, updated_row: rowNumber });
}
