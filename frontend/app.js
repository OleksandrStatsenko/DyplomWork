const API = window.API_BASE_URL || "";
const $ = (id) => document.getElementById(id);
const state = { suppliers: [], products: [] };

async function request(path, options = {}) {
  const response = await fetch(API + path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  if (!response.ok) {
    let detail = "Не вдалося виконати запит";
    try { detail = (await response.json()).detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  return response.status === 204 ? null : response.json();
}

function showMessage(message, error = false) {
  $("message").textContent = message;
  $("message").className = error ? "error" : "";
}

function renderTable(target, headers, rows) {
  const container = $(target);
  if (!rows.length) {
    container.innerHTML = '<p class="empty">Поки що записів немає.</p>';
    return;
  }
  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  headers.forEach((header) => {
    const th = document.createElement("th");
    th.textContent = header;
    headRow.append(th);
  });
  thead.append(headRow);
  const tbody = document.createElement("tbody");
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    row.forEach((value) => {
      const td = document.createElement("td");
      td.textContent = value ?? "—";
      tr.append(td);
    });
    tbody.append(tr);
  });
  table.append(thead, tbody);
  container.replaceChildren(table);
}

async function loadSuppliers() {
  state.suppliers = await request("/api/suppliers");
  renderTable("supplier-list", ["Назва", "Контакт", "Телефон", "Електронна пошта"],
    state.suppliers.map((x) => [x.name, x.contact, x.phone, x.email]));
  $("delivery-supplier").replaceChildren(...state.suppliers.map((x) => new Option(x.name, x.id)));
}

async function loadProducts() {
  state.products = await request("/api/products");
  renderTable("product-list", ["Назва", "Одиниця", "Ціна за м³", "Опис"],
    state.products.map((x) => [x.name, x.unit, x.price_per_cubic_meter, x.description]));
  $("delivery-product").replaceChildren(...state.products.map((x) => new Option(x.name, x.id)));
}

async function loadDeliveries() {
  const items = await request("/api/deliveries");
  const supplierNames = Object.fromEntries(state.suppliers.map((x) => [x.id, x.name]));
  const productNames = Object.fromEntries(state.products.map((x) => [x.id, x.name]));
  renderTable("delivery-list", ["Дата", "Постачальник", "Товар", "Кількість", "Ціна"],
    items.map((x) => [x.delivery_date, supplierNames[x.supplier_id], productNames[x.product_id], x.quantity, x.unit_price]));
}

document.querySelectorAll(".tab").forEach((button) => button.addEventListener("click", () => {
  document.querySelectorAll(".tab,.panel").forEach((item) => item.classList.remove("active"));
  button.classList.add("active");
  $(button.dataset.tab).classList.add("active");
}));

$("supplier-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await request("/api/suppliers", { method: "POST", body: JSON.stringify({
      name: $("supplier-name").value.trim(), contact: $("supplier-contact").value.trim() || null,
      phone: $("supplier-phone").value.trim() || null, email: $("supplier-email").value.trim() || null,
    }) });
    event.target.reset(); await loadSuppliers(); showMessage("Постачальника додано.");
  } catch (error) { showMessage(error.message, true); }
});

$("product-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const price = $("product-price").value;
    await request("/api/products", { method: "POST", body: JSON.stringify({
      name: $("product-name").value.trim(), unit: $("product-unit").value.trim() || null,
      price_per_cubic_meter: price ? Number(price) : null,
      description: $("product-description").value.trim() || null,
    }) });
    event.target.reset(); await loadProducts(); showMessage("Товар додано.");
  } catch (error) { showMessage(error.message, true); }
});

$("delivery-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await request("/api/deliveries", { method: "POST", body: JSON.stringify({
      supplier_id: Number($("delivery-supplier").value), product_id: Number($("delivery-product").value),
      quantity: Number($("delivery-quantity").value), delivery_date: $("delivery-date").value,
      unit_price: $("delivery-price").value ? Number($("delivery-price").value) : null,
      notes: $("delivery-notes").value.trim() || null,
    }) });
    event.target.reset(); $("delivery-date").value = new Date().toISOString().slice(0, 10);
    await loadDeliveries(); showMessage("Поставку успішно зареєстровано.");
  } catch (error) { showMessage(error.message, true); }
});

async function start() {
  try {
    await request("/health");
    $("connection").textContent = "Сервер доступний";
    $("connection").classList.add("ok");
    $("delivery-date").value = new Date().toISOString().slice(0, 10);
    await loadSuppliers(); await loadProducts(); await loadDeliveries();
  } catch (error) {
    $("connection").textContent = "Немає з’єднання з API";
    $("connection").classList.add("error");
    showMessage(error.message, true);
  }
}
start();

const voiceButton = $("voice-button");
let recorder = null;
let recordedChunks = [];
let recordingStream = null;

function setVoiceStatus(text) {
  $("recording-status").textContent = text;
}

voiceButton.addEventListener("click", async () => {
  if (recorder && recorder.state === "recording") {
    recorder.stop();
    voiceButton.disabled = true;
    voiceButton.textContent = "Обробка…";
    setVoiceStatus("Надсилаю аудіо на сервер…");
    return;
  }

  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    showMessage("Браузер не підтримує запис аудіо. Спробуйте оновити браузер.", true);
    return;
  }

  try {
    recordingStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const preferredType = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg"].find(
      (type) => MediaRecorder.isTypeSupported(type)
    );
    recorder = new MediaRecorder(recordingStream, preferredType ? { mimeType: preferredType } : {});
    recordedChunks = [];
    recorder.addEventListener("dataavailable", (event) => {
      if (event.data.size) recordedChunks.push(event.data);
    });
    recorder.addEventListener("stop", async () => {
      recordingStream.getTracks().forEach((track) => track.stop());
      const blob = new Blob(recordedChunks, { type: recorder.mimeType || "audio/webm" });
      if (!blob.size) {
        setVoiceStatus("Аудіо не записано. Спробуйте ще раз.");
        voiceButton.disabled = false;
        voiceButton.textContent = "🎙 Почати запис";
        return;
      }
      const extension = blob.type.includes("ogg") ? "ogg" : "webm";
      const form = new FormData();
      form.append("file", blob, "voice." + extension);
      try {
        const response = await fetch(API + "/api/assistant/voice", { method: "POST", body: form });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Помилка голосового запиту");
        $("voice-transcript").textContent = data.transcript;
        $("voice-reply").textContent = data.reply;
        $("voice-result").hidden = false;
        if (data.audio_base64) {
          $("voice-audio").src = "data:" + data.audio_media_type + ";base64," + data.audio_base64;
        }
        setVoiceStatus("Готово. Можете поставити наступне запитання.");
        showMessage("Голосовий запит успішно оброблено.");
      } catch (error) {
        setVoiceStatus(error.message);
        showMessage(error.message, true);
      } finally {
        voiceButton.disabled = false;
        voiceButton.textContent = "🎙 Почати запис";
      }
    }, { once: true });
    recorder.start();
    voiceButton.textContent = "■ Зупинити запис";
    setVoiceStatus("Слухаю… натисніть кнопку, щоб завершити запис.");
  } catch (error) {
    setVoiceStatus("Не вдалося отримати доступ до мікрофона.");
    showMessage("Дозвольте браузеру використовувати мікрофон.", true);
    voiceButton.disabled = false;
  }
});
