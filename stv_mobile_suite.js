// STV Mobile Offline Suite v2.0 - Premium Reader & Range Downloader for iOS
(function() {
    if (window.__stv_suite_loaded) {
        window.__stv_toggle_panel();
        return;
    }
    window.__stv_suite_loaded = true;

    // 1. Storage & Settings
    const DB_NAME = "STV_OFFLINE_DB";
    const DB_VERSION = 1;
    let dbInstance = null;

    const DEFAULT_SETTINGS = {
        theme: "sepia", // white, sepia, dark, oled
        fontSize: 19,
        lineHeight: 1.8,
        fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Roboto, sans-serif",
        textAlign: "justify",
        autoScrollSpeed: 0
    };

    let userSettings = Object.assign({}, DEFAULT_SETTINGS);
    try {
        const saved = localStorage.getItem("stv_reader_settings");
        if (saved) userSettings = Object.assign(userSettings, JSON.parse(saved));
    } catch(e) {}

    function saveSettings() {
        try {
            localStorage.setItem("stv_reader_settings", JSON.stringify(userSettings));
        } catch(e) {}
    }

    function initDB() {
        return new Promise((resolve, reject) => {
            const req = indexedDB.open(DB_NAME, DB_VERSION);
            req.onupgradeneeded = (e) => {
                const db = e.target.result;
                if (!db.objectStoreNames.contains("books")) {
                    db.createObjectStore("books", { keyPath: "id" });
                }
                if (!db.objectStoreNames.contains("chapters")) {
                    const chStore = db.createObjectStore("chapters", { keyPath: "key" });
                    chStore.createIndex("by_book", "book_id", { unique: false });
                }
            };
            req.onsuccess = (e) => {
                dbInstance = e.target.result;
                resolve(dbInstance);
            };
            req.onerror = (e) => reject(e);
        });
    }

    async function saveBookMeta(book) {
        const db = await initDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction("books", "readwrite");
            tx.objectStore("books").put(book);
            tx.oncomplete = () => resolve();
            tx.onerror = (e) => reject(e);
        });
    }

    async function saveChapter(chapter) {
        const db = await initDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction("chapters", "readwrite");
            tx.objectStore("chapters").put(chapter);
            tx.oncomplete = () => resolve();
            tx.onerror = (e) => reject(e);
        });
    }

    async function getAllBooks() {
        const db = await initDB();
        return new Promise((resolve) => {
            const tx = db.transaction("books", "readonly");
            const req = tx.objectStore("books").getAll();
            req.onsuccess = () => resolve(req.result || []);
            req.onerror = () => resolve([]);
        });
    }

    async function getChaptersForBook(bookId) {
        const db = await initDB();
        return new Promise((resolve) => {
            const tx = db.transaction("chapters", "readonly");
            const store = tx.objectStore("chapters");
            const index = store.index("by_book");
            const req = index.getAll(bookId);
            req.onsuccess = () => {
                const list = req.result || [];
                list.sort((a, b) => a.index - b.index);
                resolve(list);
            };
            req.onerror = () => resolve([]);
        });
    }

    function cleanChapterHtml(raw) {
        if (!raw) return "";
        let clean = raw.replace(/<p><span[^>]*>@Bạn đang đọc[^<]*<\/span><\/p>/gi, "");
        clean = clean.replace(/<span[^>]*style=['"][^'"]*color:gray[^'"]*['"][^>]*>.*?<\/span>/gi, "");
        clean = clean.replace(/<br\s*\/?>/gi, "\n").replace(/<\/p>/gi, "\n\n");
        const div = document.createElement("div");
        div.innerHTML = clean;
        let text = div.innerText || div.textContent || "";
        text = text.replace(/\xa0/g, " ").replace(/\n{3,}/g, "\n\n").trim();
        return text;
    }

    // 2. UI Elements (Float Button, Downloader Modal, Fullscreen Reader Modal)
    const floatBtn = document.createElement("div");
    floatBtn.id = "stv-float-btn";
    floatBtn.innerHTML = "⚡ Tải & Đọc Offline";
    floatBtn.style.cssText = `
        position: fixed;
        bottom: 75px;
        right: 14px;
        background: #2563eb;
        color: #ffffff;
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
        font-size: 13px;
        font-weight: 700;
        padding: 9px 15px;
        border-radius: 24px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.3);
        z-index: 999990;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 6px;
        user-select: none;
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
    `;

    const panel = document.createElement("div");
    panel.id = "stv-panel";
    panel.style.cssText = `
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: #ffffff;
        color: #0f172a;
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif;
        border-top-left-radius: 20px;
        border-top-right-radius: 20px;
        box-shadow: 0 -10px 40px rgba(0,0,0,0.35);
        z-index: 999995;
        padding: 18px 16px calc(env(safe-area-inset-bottom, 20px) + 10px) 16px;
        display: none;
        max-height: 88vh;
        overflow-y: auto;
    `;

    // Fullscreen Reader Modal (Like Apple Books / Kindle)
    const readerModal = document.createElement("div");
    readerModal.id = "stv-reader-modal";
    readerModal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        z-index: 1000000;
        display: none;
        flex-direction: column;
        background: #fbf0d9;
        color: #2d241e;
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", serif;
        user-select: text;
        overflow: hidden;
    `;

    document.body.appendChild(floatBtn);
    document.body.appendChild(panel);
    document.body.appendChild(readerModal);

    window.__stv_toggle_panel = function() {
        if (panel.style.display === "none" || !panel.style.display) {
            panel.style.display = "block";
            renderPanelMain();
        } else {
            panel.style.display = "none";
        }
    };

    floatBtn.onclick = window.__stv_toggle_panel;

    function detectStory() {
        const url = window.location.href;
        const m = url.match(/\/truyen\/([a-zA-Z0-9_\-]+)\/[0-9]+\/([a-zA-Z0-9_\-]+)/);
        if (m) {
            const host = m[1];
            const bookId = m[2];
            let title = document.title.replace(/\s*-\s*[0-9]+\s*chương.*$/i, "").trim();
            const h1 = document.querySelector("h1");
            if (h1 && h1.innerText) title = h1.innerText.trim();
            return { host, bookId, title, key: `${host}_${bookId}` };
        }
        return null;
    }

    let isDownloading = false;
    let cancelDownloadFlag = false;

    async function renderPanelMain() {
        const story = detectStory();
        panel.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; border-bottom:1px solid #e2e8f0; padding-bottom:8px;">
                <div style="font-size:16px; font-weight:800; color:#1e3a8a;">⚡ STV OFFLINE STUDIO v2.0</div>
                <div style="cursor:pointer; font-size:20px; font-weight:bold; color:#64748b; padding:2px 8px;" onclick="window.__stv_toggle_panel()">✕</div>
            </div>

            ${story ? `
                <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:12px; margin-bottom:12px;">
                    <div style="font-weight:700; font-size:15px; color:#0f172a; margin-bottom:2px;">📖 ${story.title}</div>
                    <div style="font-size:12px; color:#64748b; margin-bottom:10px;">Nguồn: ${story.host.toUpperCase()} • ID: ${story.bookId}</div>
                    
                    <!-- RANGE SELECTOR (TẢI THEO KHOẢNG CHƯƠNG) -->
                    <div style="background:#ffffff; border:1px solid #cbd5e1; border-radius:8px; padding:10px; margin-bottom:10px;">
                        <div style="font-size:12px; font-weight:700; color:#334155; margin-bottom:6px;">TẢI THEO KHOẢNG CHƯƠNG:</div>
                        <div style="display:flex; align-items:center; gap:6px; margin-bottom:8px;">
                            <span style="font-size:13px; color:#475569;">Từ:</span>
                            <input id="stv-range-from" type="number" value="1" min="1" style="width:65px; padding:6px; border:1px solid #cbd5e1; border-radius:6px; font-size:13px; text-align:center;">
                            <span style="font-size:13px; color:#475569;">Đến:</span>
                            <input id="stv-range-to" type="number" value="50" min="1" style="width:65px; padding:6px; border:1px solid #cbd5e1; border-radius:6px; font-size:13px; text-align:center;">
                            <button id="stv-btn-dl-range" style="flex:1; background:#2563eb; color:#fff; font-weight:700; border:none; border-radius:6px; padding:8px; font-size:13px; cursor:pointer;">
                                ⬇ Tải Khoảng
                            </button>
                        </div>

                        <!-- QUICK PRESET CHIPS -->
                        <div style="display:flex; gap:6px; flex-wrap:wrap;">
                            <span style="font-size:11px; color:#64748b; align-self:center;">Chọn nhanh:</span>
                            <button class="stv-chip" onclick="setRange(1, 20)">1 - 20</button>
                            <button class="stv-chip" onclick="setRange(1, 50)">1 - 50</button>
                            <button class="stv-chip" onclick="setRange(1, 100)">1 - 100</button>
                            <button class="stv-chip" onclick="setRangeAll()">Toàn Bộ</button>
                        </div>
                    </div>

                    <button id="stv-btn-dl-all" style="width:100%; background:#10b981; color:#fff; font-weight:700; border:none; border-radius:8px; padding:11px; font-size:14px; cursor:pointer; margin-bottom:4px;">
                        ⬇ Tải Toàn Bộ Truyện Về iPhone
                    </button>

                    <!-- PROGRESS BAR -->
                    <div id="stv-dl-progress" style="display:none; margin-top:8px;">
                        <div style="background:#e2e8f0; height:8px; border-radius:4px; overflow:hidden;">
                            <div id="stv-dl-bar" style="background:#10b981; height:100%; width:0%; transition:width 0.2s;"></div>
                        </div>
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-top:4px;">
                            <span id="stv-dl-status" style="font-size:12px; color:#475569;">Đang chuẩn bị...</span>
                            <button id="stv-btn-cancel-dl" style="background:none; border:none; color:#ef4444; font-size:12px; font-weight:700; cursor:pointer;">Dừng</button>
                        </div>
                    </div>
                </div>
            ` : `
                <div style="padding:10px 0; color:#64748b; font-size:13px; margin-bottom:12px;">
                    <i>Hãy vào trang chi tiết một bộ truyện bất kỳ trên Sáng Tác Việt để chọn tải từ chương nào đến chương nào.</i>
                </div>
            `}

            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:8px;">
                <button id="stv-btn-open-lib" style="background:#4f46e5; color:#fff; font-weight:700; border:none; border-radius:8px; padding:12px; font-size:13px; cursor:pointer;">
                    📖 Mở Tủ Sách Offline
                </button>
                <button id="stv-btn-export-txt" style="background:#fff; color:#2563eb; border:1px solid #2563eb; font-weight:700; border-radius:8px; padding:12px; font-size:13px; cursor:pointer;">
                    📥 Xuất File TXT
                </button>
            </div>
            <div id="stv-sub-view" style="margin-top:14px;"></div>
        `;

        // Style helper for preset chips
        const chips = panel.querySelectorAll(".stv-chip");
        chips.forEach(c => {
            c.style.cssText = "background:#f1f5f9; border:1px solid #cbd5e1; border-radius:4px; padding:3px 8px; font-size:11px; font-weight:600; cursor:pointer; color:#334155;";
        });

        window.setRange = (from, to) => {
            document.getElementById("stv-range-from").value = from;
            document.getElementById("stv-range-to").value = to;
        };

        window.setRangeAll = () => {
            document.getElementById("stv-range-from").value = 1;
            document.getElementById("stv-range-to").value = 99999;
        };

        if (story) {
            document.getElementById("stv-btn-dl-all").onclick = () => runDownload(story, 1, 99999);
            document.getElementById("stv-btn-dl-range").onclick = () => {
                const f = parseInt(document.getElementById("stv-range-from").value) || 1;
                const t = parseInt(document.getElementById("stv-range-to").value) || 99999;
                runDownload(story, f, t);
            };
            document.getElementById("stv-btn-export-txt").onclick = () => exportStoryTxt(story);
            document.getElementById("stv-btn-cancel-dl").onclick = () => {
                cancelDownloadFlag = true;
            };
        }
        document.getElementById("stv-btn-open-lib").onclick = renderOfflineLibrary;
    }

    async function runDownload(story, fromIndex, toIndex) {
        if (isDownloading) {
            alert("Tiến trình tải khác đang chạy!");
            return;
        }

        isDownloading = true;
        cancelDownloadFlag = false;

        const progBox = document.getElementById("stv-dl-progress");
        const progBar = document.getElementById("stv-dl-bar");
        const progText = document.getElementById("stv-dl-status");
        progBox.style.display = "block";
        progText.innerText = "Đang lấy danh mục chương...";

        try {
            const clRes = await fetch(`/index.php?ngmar=chapterlist&h=${story.host}&bookid=${story.bookId}&sajax=getchapterlist`);
            const clData = await clRes.json();
            if (clData.code !== 1 || !clData.data) {
                alert("Không lấy được danh sách chương từ máy chủ!");
                isDownloading = false;
                progBox.style.display = "none";
                return;
            }

            const rawItems = clData.data.split("-//-").filter(x => x.trim());
            const allChapters = [];
            rawItems.forEach((item, idx) => {
                const parts = item.split("-/-");
                if (parts.length >= 2) {
                    allChapters.push({
                        cid: parts[1].trim(),
                        title: parts[2] ? parts[2].trim() : `Chương ${idx + 1}`,
                        index: idx + 1
                    });
                }
            });

            // Filter by requested range
            const targetChapters = allChapters.filter(c => c.index >= fromIndex && c.index <= toIndex);
            if (!targetChapters.length) {
                alert(`Không tìm thấy chương nào trong khoảng ${fromIndex} - ${toIndex}!`);
                isDownloading = false;
                progBox.style.display = "none";
                return;
            }

            // Save book metadata
            await saveBookMeta({
                id: story.key,
                host: story.host,
                bookId: story.bookId,
                title: story.title,
                total: allChapters.length,
                downloaded: 0,
                updatedAt: new Date().toISOString()
            });

            let success = 0;
            const total = targetChapters.length;

            for (let i = 0; i < total; i++) {
                if (cancelDownloadFlag) {
                    progText.innerText = `Đã tạm dừng tải. Đã lưu ${success} chương.`;
                    break;
                }

                const ch = targetChapters[i];
                const pct = Math.round(((i + 1) / total) * 100);
                progBar.style.width = pct + "%";
                progText.innerText = `[${i + 1}/${total} - ${pct}%] Đang tải: ${ch.title}...`;

                try {
                    const r = await fetch(`/index.php?bookid=${story.bookId}&h=${story.host}&c=${ch.cid}&ngmar=readc&sajax=readchapter&sty=1&exts=`, {
                        method: "POST",
                        headers: { "Content-Type": "application/x-www-form-urlencoded" },
                        body: ""
                    });
                    const d = await r.json();
                    if ((d.code == 0 || d.code === "0") && d.data) {
                        const cleanText = cleanChapterHtml(d.data);
                        const chObj = {
                            key: `${story.key}_${ch.cid}`,
                            book_id: story.key,
                            chapter_id: ch.cid,
                            index: ch.index,
                            title: (d.chaptername || ch.title).trim(),
                            content: cleanText
                        };
                        await saveChapter(chObj);
                        try {
                            localStorage.setItem(`stv_chap_${story.key}_${ch.cid}`, cleanText);
                            localStorage.setItem(`stv_title_${story.key}_${ch.cid}`, chObj.title);
                        } catch(e) {}
                        success++;
                    }
                } catch(err) {
                    console.error("Fetch chapter err:", err);
                }

                // Micro pause ~150ms
                await new Promise(r => setTimeout(r, 150));
            }

            // Update book meta count
            const savedList = await getChaptersForBook(story.key);
            await saveBookMeta({
                id: story.key,
                host: story.host,
                bookId: story.bookId,
                title: story.title,
                total: allChapters.length,
                downloaded: savedList.length,
                updatedAt: new Date().toISOString()
            });

            progText.innerText = `✅ Hoàn tất! Đã tải ${success}/${total} chương vào bộ nhớ iPhone.`;
            alert(`✅ Đã tải thành công ${success} chương (từ chương ${fromIndex} đến ${toIndex}) của bộ truyện '${story.title}' vào iPhone! Sếp có thể tắt mạng và mở Tủ Sách Offline để đọc.`);
        } catch (e) {
            alert("Lỗi tải: " + e);
        } finally {
            isDownloading = false;
        }
    }

    async function renderOfflineLibrary() {
        const sub = document.getElementById("stv-sub-view");
        const books = await getAllBooks();
        if (!books.length) {
            sub.innerHTML = `<div style="text-align:center; color:#64748b; padding:16px;">Chưa có bộ truyện nào được lưu trong máy iPhone.</div>`;
            return;
        }

        sub.innerHTML = `
            <div style="font-weight:700; font-size:14px; margin-bottom:8px; color:#1e3a8a;">📚 Các Bộ Truyện Đã Lưu Trong Máy:</div>
            ${books.map(b => `
                <div style="background:#f1f5f9; border-radius:8px; padding:10px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
                    <div style="flex:1; padding-right:8px;">
                        <div style="font-weight:700; font-size:14px; color:#0f172a;">${b.title}</div>
                        <div style="font-size:12px; color:#64748b;">Đã lưu: ${b.downloaded || 0} / ${b.total || 0} chương</div>
                    </div>
                    <button style="background:#2563eb; color:#fff; border:none; border-radius:6px; padding:8px 14px; font-weight:700; font-size:13px; cursor:pointer;" onclick="window.__stv_open_reader('${b.id}')">
                        Đọc Ngay
                    </button>
                </div>
            `).join("")}
        `;
    }

    // 3. FULLSCREEN PREMIUM NOVEL READER ENGINE
    let activeChapters = [];
    let activeChapterIndex = 0;
    let autoScrollInterval = null;
    let showControls = true;

    window.__stv_open_reader = async function(bookKey) {
        panel.style.display = "none";
        activeChapters = await getChaptersForBook(bookKey);
        if (!activeChapters.length) {
            alert("Chưa có chương nào được lưu cho bộ truyện này!");
            return;
        }

        // Remember last read position
        let lastIdx = 0;
        try {
            const savedIdx = localStorage.getItem(`stv_last_read_${bookKey}`);
            if (savedIdx) lastIdx = parseInt(savedIdx) || 0;
            if (lastIdx >= activeChapters.length) lastIdx = 0;
        } catch(e) {}

        readerModal.style.display = "flex";
        renderFullReader(lastIdx);
    };

    function getThemeStyles(theme) {
        switch(theme) {
            case "white":
                return { bg: "#ffffff", text: "#0f172a", border: "#e2e8f0", topBar: "rgba(255,255,255,0.95)" };
            case "dark":
                return { bg: "#1e293b", text: "#f1f5f9", border: "#334155", topBar: "rgba(30,41,59,0.95)" };
            case "oled":
                return { bg: "#000000", text: "#94a3b8", border: "#262626", topBar: "rgba(0,0,0,0.95)" };
            case "sepia":
            default:
                return { bg: "#fbf0d9", text: "#2d241e", border: "#e5d5be", topBar: "rgba(251,240,217,0.95)" };
        }
    }

    function renderFullReader(index) {
        activeChapterIndex = index;
        const ch = activeChapters[index];
        const theme = getThemeStyles(userSettings.theme);

        // Save last read chapter index
        try {
            localStorage.setItem(`stv_last_read_${ch.book_id}`, index);
        } catch(e) {}

        readerModal.style.backgroundColor = theme.bg;
        readerModal.style.color = theme.text;

        const paras = ch.content.split("\n\n").map(p => {
            const clean = p.trim();
            return clean ? `<p style="margin-bottom:1.3em; text-indent:1.6em;">${clean.replace(/\n/g, "<br>")}</p>` : "";
        }).join("");

        readerModal.innerHTML = `
            <!-- TOP APP BAR -->
            <div id="stv-reader-top" style="position:fixed; top:0; left:0; right:0; padding:calc(env(safe-area-inset-top, 20px) + 8px) 16px 10px 16px; background:${theme.topBar}; backdrop-filter:blur(10px); -webkit-backdrop-filter:blur(10px); border-bottom:1px solid ${theme.border}; display:flex; justify-content:space-between; align-items:center; z-index:1000002; transition:transform 0.25s ease;">
                <button id="stv-reader-btn-back" style="background:none; border:none; font-size:15px; font-weight:700; color:#2563eb; cursor:pointer;">
                    ⬅ Tủ Sách
                </button>
                <div style="font-size:13px; font-weight:700; color:${theme.text}; opacity:0.8; max-width:55%; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
                    ${ch.title}
                </div>
                <div style="display:flex; gap:10px; align-items:center;">
                    <button id="stv-btn-toggle-drawer" style="background:none; border:none; font-size:18px; cursor:pointer;">📑</button>
                    <button id="stv-btn-toggle-settings" style="background:none; border:none; font-size:18px; cursor:pointer;">Aa</button>
                </div>
            </div>

            <!-- READING SCROLL CONTAINER -->
            <div id="stv-reader-scroll" style="flex:1; overflow-y:auto; padding:calc(env(safe-area-inset-top, 20px) + 60px) 20px calc(env(safe-area-inset-bottom, 20px) + 60px) 20px; font-family:${userSettings.fontFamily}; font-size:${userSettings.fontSize}px; line-height:${userSettings.lineHeight}; text-align:${userSettings.textAlign};">
                <div style="font-size:${userSettings.fontSize * 1.3}px; font-weight:800; text-align:center; margin-bottom:24px; padding-bottom:12px; border-bottom:1px solid ${theme.border}; color:${theme.text};">
                    ${ch.title}
                </div>
                <div id="stv-reader-body-text">
                    ${paras || "<i>(Chương chưa có nội dung)</i>"}
                </div>
                
                <!-- NEXT / PREV BUTTONS IN CONTENT -->
                <div style="display:flex; justify-content:space-between; gap:12px; margin-top:40px; padding-top:20px; border-top:1px solid ${theme.border};">
                    <button id="stv-content-prev" style="flex:1; padding:12px; background:rgba(0,0,0,0.06); border:1px solid ${theme.border}; border-radius:10px; color:${theme.text}; font-weight:700; font-size:14px;" ${index <= 0 ? "disabled" : ""}>
                        ⏮ Chương Trước
                    </button>
                    <button id="stv-content-next" style="flex:1; padding:12px; background:#2563eb; color:#fff; border:none; border-radius:10px; font-weight:700; font-size:14px;" ${index >= activeChapters.length - 1 ? "disabled" : ""}>
                        Chương Sau ⏭
                    </button>
                </div>
            </div>

            <!-- BOTTOM APP BAR -->
            <div id="stv-reader-bottom" style="position:fixed; bottom:0; left:0; right:0; padding:10px 16px calc(env(safe-area-inset-bottom, 20px) + 8px) 16px; background:${theme.topBar}; backdrop-filter:blur(10px); -webkit-backdrop-filter:blur(10px); border-top:1px solid ${theme.border}; display:flex; justify-content:space-between; align-items:center; z-index:1000002; transition:transform 0.25s ease;">
                <button id="stv-bar-prev" style="background:none; border:none; font-size:14px; font-weight:700; color:#2563eb; cursor:pointer;" ${index <= 0 ? "disabled" : ""}>
                    ⏮ Trước
                </button>
                <div style="font-size:12px; font-weight:700; color:${theme.text}; opacity:0.7;">
                    ${index + 1} / ${activeChapters.length}
                </div>
                <button id="stv-bar-autoscroll" style="background:none; border:none; font-size:13px; font-weight:700; color:#10b981; cursor:pointer;">
                    ▶ Tự Cuộn
                </button>
                <button id="stv-bar-next" style="background:none; border:none; font-size:14px; font-weight:700; color:#2563eb; cursor:pointer;" ${index >= activeChapters.length - 1 ? "disabled" : ""}>
                    Sau ⏭
                </button>
            </div>

            <!-- SETTINGS DRAWER SHEET (Aa) -->
            <div id="stv-settings-sheet" style="position:fixed; bottom:0; left:0; right:0; background:${theme.bg}; color:${theme.text}; border-top-left-radius:20px; border-top-right-radius:20px; box-shadow:0 -10px 30px rgba(0,0,0,0.3); z-index:1000005; padding:20px 20px calc(env(safe-area-inset-bottom, 20px) + 15px) 20px; display:none;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
                    <span style="font-size:15px; font-weight:800;">⚙️ Cài Đặt Giao Diện Đọc</span>
                    <button id="stv-close-settings" style="background:none; border:none; font-size:18px; font-weight:bold; color:${theme.text};">✕</button>
                </div>

                <!-- THEME SELECTOR -->
                <div style="margin-bottom:16px;">
                    <div style="font-size:12px; font-weight:700; opacity:0.7; margin-bottom:8px;">MÀU NỀN TRANG ĐỌC:</div>
                    <div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:8px;">
                        <button class="stv-theme-btn" data-theme="sepia" style="background:#fbf0d9; color:#2d241e; border:2px solid ${userSettings.theme === 'sepia' ? '#2563eb' : '#e5d5be'}; border-radius:8px; padding:10px 0; font-weight:700; font-size:12px;">Giấy Vàng</button>
                        <button class="stv-theme-btn" data-theme="white" style="background:#ffffff; color:#0f172a; border:2px solid ${userSettings.theme === 'white' ? '#2563eb' : '#cbd5e1'}; border-radius:8px; padding:10px 0; font-weight:700; font-size:12px;">Sáng</button>
                        <button class="stv-theme-btn" data-theme="dark" style="background:#1e293b; color:#f1f5f9; border:2px solid ${userSettings.theme === 'dark' ? '#2563eb' : '#334155'}; border-radius:8px; padding:10px 0; font-weight:700; font-size:12px;">Xám Êm</button>
                        <button class="stv-theme-btn" data-theme="oled" style="background:#000000; color:#94a3b8; border:2px solid ${userSettings.theme === 'oled' ? '#2563eb' : '#333333'}; border-radius:8px; padding:10px 0; font-weight:700; font-size:12px;">OLED</button>
                    </div>
                </div>

                <!-- FONT SIZE CONTROLS -->
                <div style="margin-bottom:16px;">
                    <div style="font-size:12px; font-weight:700; opacity:0.7; margin-bottom:8px;">CỠ CHỮ (FONT SIZE):</div>
                    <div style="display:flex; align-items:center; gap:12px;">
                        <button id="stv-font-dec" style="flex:1; background:rgba(0,0,0,0.06); border:1px solid ${theme.border}; border-radius:8px; padding:10px; font-weight:800; font-size:14px; color:${theme.text};">A -</button>
                        <span id="stv-font-val" style="font-weight:700; font-size:15px; width:45px; text-align:center;">${userSettings.fontSize}px</span>
                        <button id="stv-font-inc" style="flex:1; background:rgba(0,0,0,0.06); border:1px solid ${theme.border}; border-radius:8px; padding:10px; font-weight:800; font-size:14px; color:${theme.text};">A +</button>
                    </div>
                </div>

                <!-- LINE HEIGHT CONTROLS -->
                <div>
                    <div style="font-size:12px; font-weight:700; opacity:0.7; margin-bottom:8px;">GIÃN DÒNG (LINE SPACING):</div>
                    <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:8px;">
                        <button class="stv-line-btn" data-line="1.5" style="background:rgba(0,0,0,0.06); border:1px solid ${theme.border}; border-radius:8px; padding:8px; font-weight:700; font-size:12px; color:${theme.text};">1.5x Dày</button>
                        <button class="stv-line-btn" data-line="1.8" style="background:rgba(0,0,0,0.06); border:1px solid ${theme.border}; border-radius:8px; padding:8px; font-weight:700; font-size:12px; color:${theme.text};">1.8x Vừa</button>
                        <button class="stv-line-btn" data-line="2.2" style="background:rgba(0,0,0,0.06); border:1px solid ${theme.border}; border-radius:8px; padding:8px; font-weight:700; font-size:12px; color:${theme.text};">2.2x Thoáng</button>
                    </div>
                </div>
            </div>

            <!-- CHAPTERS DRAWER SHEET (📑) -->
            <div id="stv-drawer-sheet" style="position:fixed; top:0; bottom:0; left:0; width:80%; max-width:320px; background:${theme.bg}; color:${theme.text}; border-right:1px solid ${theme.border}; box-shadow:10px 0 30px rgba(0,0,0,0.3); z-index:1000005; display:none; flex-direction:column; padding-top:calc(env(safe-area-inset-top, 20px) + 10px);">
                <div style="display:flex; justify-content:space-between; align-items:center; padding:12px 16px; border-bottom:1px solid ${theme.border};">
                    <span style="font-size:15px; font-weight:800;">📑 Danh Sách Chương</span>
                    <button id="stv-close-drawer" style="background:none; border:none; font-size:18px; font-weight:bold; color:${theme.text};">✕</button>
                </div>
                <div id="stv-drawer-list" style="flex:1; overflow-y:auto; padding:10px 14px;">
                    ${activeChapters.map((c, i) => `
                        <div class="stv-drawer-item" data-idx="${i}" style="padding:10px; border-radius:6px; font-size:13px; font-weight:${i === index ? '700' : '500'}; color:${i === index ? '#2563eb' : theme.text}; background:${i === index ? 'rgba(37,99,235,0.1)' : 'transparent'}; cursor:pointer; margin-bottom:4px;">
                            ${c.title}
                        </div>
                    `).join("")}
                </div>
            </div>
        `;

        const scrollContainer = document.getElementById("stv-reader-scroll");
        const topBar = document.getElementById("stv-reader-top");
        const bottomBar = document.getElementById("stv-reader-bottom");
        const settingsSheet = document.getElementById("stv-settings-sheet");
        const drawerSheet = document.getElementById("stv-drawer-sheet");

        // Back to library
        document.getElementById("stv-reader-btn-back").onclick = () => {
            stopAutoScroll();
            readerModal.style.display = "none";
            window.__stv_toggle_panel();
        };

        // Navigation actions
        const gotoPrev = () => {
            stopAutoScroll();
            if (activeChapterIndex > 0) renderFullReader(activeChapterIndex - 1);
        };
        const gotoNext = () => {
            stopAutoScroll();
            if (activeChapterIndex < activeChapters.length - 1) renderFullReader(activeChapterIndex + 1);
        };

        document.getElementById("stv-bar-prev").onclick = gotoPrev;
        document.getElementById("stv-bar-next").onclick = gotoNext;
        document.getElementById("stv-content-prev").onclick = gotoPrev;
        document.getElementById("stv-content-next").onclick = gotoNext;

        // Toggle toolbars on center tap
        scrollContainer.onclick = (e) => {
            // Ignore if clicked on buttons
            if (e.target.tagName === 'BUTTON') return;
            showControls = !showControls;
            topBar.style.transform = showControls ? "translateY(0)" : "translateY(-100%)";
            bottomBar.style.transform = showControls ? "translateY(0)" : "translateY(100%)";
        };

        // Settings Sheet Actions
        document.getElementById("stv-btn-toggle-settings").onclick = () => {
            settingsSheet.style.display = "block";
        };
        document.getElementById("stv-close-settings").onclick = () => {
            settingsSheet.style.display = "none";
        };

        document.querySelectorAll(".stv-theme-btn").forEach(btn => {
            btn.onclick = () => {
                userSettings.theme = btn.getAttribute("data-theme");
                saveSettings();
                renderFullReader(activeChapterIndex);
            };
        });

        document.getElementById("stv-font-inc").onclick = () => {
            if (userSettings.fontSize < 34) {
                userSettings.fontSize += 2;
                saveSettings();
                renderFullReader(activeChapterIndex);
            }
        };
        document.getElementById("stv-font-dec").onclick = () => {
            if (userSettings.fontSize > 13) {
                userSettings.fontSize -= 2;
                saveSettings();
                renderFullReader(activeChapterIndex);
            }
        };

        document.querySelectorAll(".stv-line-btn").forEach(btn => {
            btn.onclick = () => {
                userSettings.lineHeight = parseFloat(btn.getAttribute("data-line"));
                saveSettings();
                renderFullReader(activeChapterIndex);
            };
        });

        // Drawer Actions (Table of Contents)
        document.getElementById("stv-btn-toggle-drawer").onclick = () => {
            drawerSheet.style.display = "flex";
        };
        document.getElementById("stv-close-drawer").onclick = () => {
            drawerSheet.style.display = "none";
        };
        document.querySelectorAll(".stv-drawer-item").forEach(item => {
            item.onclick = () => {
                const idx = parseInt(item.getAttribute("data-idx"));
                drawerSheet.style.display = "none";
                renderFullReader(idx);
            };
        });

        // Auto-Scroll Feature
        const btnAuto = document.getElementById("stv-bar-autoscroll");
        let isAutoScrolling = false;
        function stopAutoScroll() {
            if (autoScrollInterval) {
                clearInterval(autoScrollInterval);
                autoScrollInterval = null;
            }
            isAutoScrolling = false;
            if (btnAuto) {
                btnAuto.innerText = "▶ Tự Cuộn";
                btnAuto.style.color = "#10b981";
            }
        }

        btnAuto.onclick = () => {
            if (isAutoScrolling) {
                stopAutoScroll();
            } else {
                isAutoScrolling = true;
                btnAuto.innerText = "⏸ Dừng Cuộn";
                btnAuto.style.color = "#ef4444";
                autoScrollInterval = setInterval(() => {
                    scrollContainer.scrollTop += 1;
                    if (scrollContainer.scrollTop + scrollContainer.clientHeight >= scrollContainer.scrollHeight - 10) {
                        stopAutoScroll();
                    }
                }, 30);
            }
        };
    }

    async function exportStoryTxt(story) {
        const chapters = await getChaptersForBook(story.key);
        if (!chapters.length) {
            alert("Chưa có chương nào được lưu để xuất file!");
            return;
        }

        let fullText = `=== ${story.title} ===\nNguồn: Sáng Tác Việt (${story.host.toUpperCase()})\nTổng số chương: ${chapters.length}\n${'='.repeat(40)}\n\n`;
        chapters.forEach(c => {
            fullText += `\n\n${'='.repeat(30)}\n${c.title}\n${'='.repeat(30)}\n\n${c.content}\n`;
        });

        const blob = new Blob([fullText], { type: "text/plain;charset=utf-8" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `${story.title}_Offline.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }

    // Auto open panel first time
    window.__stv_toggle_panel();
})();
