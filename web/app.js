// Chat + continuous-scroll PDF viewer: ask a question, click a citation, see
// it highlighted on the exact page. Pages are rendered lazily (only when
// scrolled near) so this stays fast even on a 300+ page PDF.

pdfjsLib.GlobalWorkerOptions.workerSrc =
  "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";

const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("ask-form");
const questionEl = document.getElementById("question");
const askButtonEl = document.getElementById("ask-button");
const pdfContainerEl = document.getElementById("pdf-container");
const documentPickerEl = document.getElementById("document-picker");
const pageIndicatorEl = document.getElementById("page-indicator");

const SCALE = 1.5; // fixed render scale; used to convert PyMuPDF bbox (points) -> canvas pixels

let loadedDocId = null;
let pdfDoc = null;
let pageWrappers = []; // one entry per page: { pageNumber, wrapper, canvas, overlay, rendered }
let pendingHighlights = {}; // page number -> highlight, for the citation currently being viewed
let intersectionObserver = null;

// --- Chat ---

formEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = questionEl.value.trim();
  if (!question) return;

  document.querySelector(".empty-state")?.remove();
  addMessage(question, "question");
  questionEl.value = "";
  askButtonEl.disabled = true;

  const loadingDiv = addMessage("Thinking...", "answer loading");

  try {
    const response = await fetch("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const data = await response.json();
    loadingDiv.remove();
    addAnswerMessage(data.answer, data.citations);
  } finally {
    askButtonEl.disabled = false;
  }
});

function addMessage(text, className) {
  const div = document.createElement("div");
  div.className = `message ${className}`;
  div.textContent = text;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

function addAnswerMessage(answer, citations) {
  const div = document.createElement("div");
  div.className = "message answer";

  // Turn "[1]", "[2]"... in the answer text into clickable badges.
  const parts = answer.split(/(\[\d+\])/g);
  parts.forEach((part) => {
    const match = part.match(/^\[(\d+)\]$/);
    if (match) {
      const num = Number(match[1]);
      const citation = citations.find((c) => c.number === num);
      const badge = document.createElement("button");
      badge.className = "citation-badge";
      badge.textContent = part;
      badge.onclick = () => showCitation(citation);
      div.appendChild(badge);
    } else {
      div.appendChild(document.createTextNode(part));
    }
  });

  if (citations.length) {
    const list = document.createElement("div");
    list.className = "citation-list";
    citations.forEach((c) => {
      const chip = document.createElement("span");
      chip.className = "citation-chip";
      chip.textContent = `[${c.number}] ${c.document_id} p.${c.page_start}-${c.page_end}`;
      chip.onclick = () => showCitation(c);
      list.appendChild(chip);
    });
    div.appendChild(list);
  }

  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

// --- PDF viewer (continuous scroll, lazily rendered) ---

async function loadDocument(documentId) {
  pdfDoc = await pdfjsLib.getDocument(`/pdf/${documentId}`).promise;
  loadedDocId = documentId;
  pendingHighlights = {};
  buildPageWrappers();
}

function buildPageWrappers() {
  intersectionObserver?.disconnect();
  pdfContainerEl.innerHTML = "";
  pageWrappers = [];

  for (let pageNumber = 1; pageNumber <= pdfDoc.numPages; pageNumber++) {
    const wrapper = document.createElement("div");
    wrapper.className = "pdf-page-wrapper";
    wrapper.dataset.page = String(pageNumber);

    const canvas = document.createElement("canvas");
    wrapper.appendChild(canvas);

    const overlay = document.createElement("div");
    overlay.className = "highlight-overlay";
    overlay.hidden = true;
    wrapper.appendChild(overlay);

    pdfContainerEl.appendChild(wrapper);
    pageWrappers.push({ pageNumber, wrapper, canvas, overlay, rendered: false });
  }

  intersectionObserver = new IntersectionObserver(onPagesIntersecting, {
    root: pdfContainerEl,
    rootMargin: "400px 0px", // render a bit before the page is actually visible
  });
  pageWrappers.forEach((pw) => intersectionObserver.observe(pw.wrapper));

  pageIndicatorEl.textContent = `${pdfDoc.numPages} pages`;
}

function onPagesIntersecting(entries) {
  let mostVisible = null;
  entries.forEach((entry) => {
    const pageNumber = Number(entry.target.dataset.page);
    if (entry.isIntersecting) {
      renderPageIfNeeded(pageNumber);
      if (!mostVisible || entry.intersectionRatio > mostVisible.ratio) {
        mostVisible = { pageNumber, ratio: entry.intersectionRatio };
      }
    }
  });
  if (mostVisible) {
    pageIndicatorEl.textContent = `Page ${mostVisible.pageNumber} / ${pdfDoc.numPages}`;
  }
}

async function renderPageIfNeeded(pageNumber) {
  const pw = pageWrappers[pageNumber - 1];
  if (!pw || pw.rendered) return;
  pw.rendered = true; // set before await so scroll events don't trigger a double render

  const page = await pdfDoc.getPage(pageNumber);
  const viewport = page.getViewport({ scale: SCALE });
  pw.canvas.width = viewport.width;
  pw.canvas.height = viewport.height;
  await page.render({ canvasContext: pw.canvas.getContext("2d"), viewport }).promise;

  drawHighlightIfQueued(pageNumber);
}

function drawHighlightIfQueued(pageNumber) {
  const pw = pageWrappers[pageNumber - 1];
  const highlight = pendingHighlights[pageNumber];
  if (!pw || !highlight) return;

  // PyMuPDF bboxes are already top-left-origin, y-down (in PDF points), the
  // same orientation as canvas pixels — so we only need to scale, not flip.
  const [x0, y0, x1, y1] = highlight.bbox;
  pw.overlay.style.left = `${x0 * SCALE}px`;
  pw.overlay.style.top = `${y0 * SCALE}px`;
  pw.overlay.style.width = `${(x1 - x0) * SCALE}px`;
  pw.overlay.style.height = `${(y1 - y0) * SCALE}px`;
  pw.overlay.hidden = false;
}

function clearHighlights() {
  pageWrappers.forEach((pw) => { pw.overlay.hidden = true; });
  pendingHighlights = {};
}

async function showCitation(citation) {
  if (!citation || !citation.highlights.length) return;

  if (loadedDocId !== citation.document_id) {
    documentPickerEl.value = citation.document_id;
    await loadDocument(citation.document_id);
  }

  clearHighlights();
  citation.highlights.forEach((h) => { pendingHighlights[h.page] = h; });

  const firstPage = citation.highlights[0].page;
  await renderPageIfNeeded(firstPage); // force-render even if not yet scrolled into view
  pageWrappers[firstPage - 1].wrapper.scrollIntoView({ behavior: "smooth", block: "center" });
}

// --- Document picker ---

async function refreshDocumentPicker() {
  const response = await fetch("/documents");
  const documents = await response.json();

  documentPickerEl.innerHTML = "";
  documents.forEach((docId) => {
    const option = document.createElement("option");
    option.value = docId;
    option.textContent = docId;
    documentPickerEl.appendChild(option);
  });

  return documents;
}

documentPickerEl.addEventListener("change", () => {
  loadDocument(documentPickerEl.value);
});

// Auto-load the first available PDF on page load, so the panel isn't empty.
(async function init() {
  const documents = await refreshDocumentPicker();
  if (documents.length) {
    documentPickerEl.value = documents[0];
    await loadDocument(documents[0]);
  }
})();
