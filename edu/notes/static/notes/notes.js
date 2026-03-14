// Notes panel behavior script.
document.addEventListener("DOMContentLoaded", function () {
    // Cache the document body for class toggles.
    const bodyEl = document.body;
    // Locate the notes panel container.
    const panelEl = document.querySelector("[data-notes-panel]");
    // Abort setup if the panel is missing.
    if (!panelEl) return;

    // Grab the open button in the topbar.
    const openBtn = document.getElementById("notes-open-btn");
    // Grab the close button inside the panel.
    const closeBtn = panelEl.querySelector("[data-notes-close]");
    // Grab the delete button inside the panel.
    const deleteBtn = panelEl.querySelector("[data-notes-delete]");
    // Grab the backdrop element.
    const backdropEl = document.querySelector("[data-notes-backdrop]");
    // Grab the sidebar element.
    const sidebarEl = panelEl.querySelector("[data-notes-sidebar]");
    // Grab the sidebar toggle button.
    const sidebarToggleBtn = panelEl.querySelector("[data-notes-sidebar-toggle]");
    // Grab the clear filter button.
    const clearFilterBtn = panelEl.querySelector("[data-notes-clear-filter]");
    // Grab the filter label element.
    const filterLabelEl = panelEl.querySelector("[data-notes-filter-label]");
    // Grab the notes list container.
    const listEl = panelEl.querySelector("[data-notes-list]");
    // Grab the empty state element.
    const emptyEl = panelEl.querySelector("[data-notes-empty]");
    // Grab the editor mount element.
    const editorMountEl = document.getElementById("notes-editor");
    // Grab the save modal overlay.
    const saveModalEl = panelEl.querySelector("[data-notes-save-modal]");
    // Grab the title input for save prompt.
    const titleInputEl = panelEl.querySelector("[data-notes-title-input]");
    // Grab the tag input for save prompt.
    const tagInputEl = panelEl.querySelector("[data-notes-tag-input]");
    // Grab the save button inside modal.
    const saveBtn = panelEl.querySelector("[data-notes-save]");
    // Grab the exit button inside modal.
    const exitBtn = panelEl.querySelector("[data-notes-exit]");
    // Grab the save error message element.
    const saveErrorEl = panelEl.querySelector("[data-notes-save-error]");
    // Collect the color buttons for text color selection.
    const colorButtons = Array.from(panelEl.querySelectorAll("[data-notes-color]"));

    // Read the list endpoint URL from data attributes.
    const listUrl = panelEl.dataset.notesListUrl || "";
    // Read the detail endpoint URL template from data attributes.
    const detailUrlTemplate = panelEl.dataset.notesDetailUrlTemplate || "";

    // Store the Quill editor instance.
    let quill = null;
    // Track the currently open note ID.
    let currentNoteId = null;
    // Track whether the editor has unsaved changes.
    let isDirty = false;
    // Track whether the user has typed in the editor at least once.
    let hasUserTyped = false;
    // Track autosave debounce timer ID.
    let autosaveTimer = null;
    // Track the active tag filter slug.
    let activeTagSlug = "";
    // Remember the last known editor selection to restore focus safely.
    let lastSelection = null;
    // Track the overlay layer for code copy buttons.
    let copyOverlayLayer = null;
    // Track a pending overlay update frame.
    let copyOverlayRaf = null;

    // Return true when shortcuts should be ignored (mobile).
    const shortcutsDisabled = () => {
        // Disable shortcuts on small screens.
        return window.matchMedia("(max-width: 900px)").matches;
    };

    // Read a cookie by name for CSRF protection.
    const getCookie = (name) => {
        // Split document cookies into key-value pairs.
        const cookies = document.cookie ? document.cookie.split("; ") : [];
        // Loop through cookies to find a matching name.
        for (const c of cookies) {
            // Split the cookie into key and value parts.
            const [key, ...rest] = c.split("=");
            // Return decoded value when name matches.
            if (key === name) return decodeURIComponent(rest.join("="));
        }
        // Return an empty string when not found.
        return "";
    };

    // Build the detail URL for a specific note ID.
    const buildDetailUrl = (noteId) => {
        // Replace the placeholder "0" with the actual note ID.
        return detailUrlTemplate.replace("0", String(noteId));
    };

    // Toggle the notes panel open/closed.
    const setPanelOpen = (isOpen) => {
        // Toggle the body class for open state.
        bodyEl.classList.toggle("notes-open", isOpen);
        // Update panel aria-hidden state.
        panelEl.setAttribute("aria-hidden", String(!isOpen));
        // Update the launcher button expanded state.
        if (openBtn) openBtn.setAttribute("aria-expanded", String(isOpen));
        // Toggle backdrop visibility.
        if (backdropEl) backdropEl.hidden = !isOpen;
    };

    // Toggle the sidebar open/closed.
    const setSidebarOpen = (isOpen) => {
        // Toggle sidebar-open class on panel.
        panelEl.classList.toggle("notes-sidebar-open", isOpen);
        // Update sidebar aria-hidden state.
        if (sidebarEl) sidebarEl.setAttribute("aria-hidden", String(!isOpen));
        // Update sidebar toggle button expanded state.
        if (sidebarToggleBtn) sidebarToggleBtn.setAttribute("aria-expanded", String(isOpen));
    };

    // Clear editor content and reset state for a new note.
    const resetEditor = () => {
        // Guard against missing editor.
        if (!quill) return;
        // Clear the editor contents.
        quill.setText("");
        // Reset text color formatting to default.
        quill.format("color", false);
        // Clear any active color button state.
        colorButtons.forEach((btn) => btn.classList.remove("is-active"));
        // Reset current note tracking.
        currentNoteId = null;
        // Reset dirty state.
        isDirty = false;
        // Clear last known selection on reset.
        lastSelection = null;
        // Disable delete button for new notes.
        if (deleteBtn) deleteBtn.disabled = true;
    };

    // Show the save modal for unsaved notes.
    const showSaveModal = () => {
        // Guard against missing modal.
        if (!saveModalEl) return;
        // Reset any prior error message.
        if (saveErrorEl) {
            saveErrorEl.textContent = "";
            saveErrorEl.hidden = true;
        }
        // Clear title input before prompting.
        if (titleInputEl) titleInputEl.value = "";
        // Clear tag input before prompting.
        if (tagInputEl) tagInputEl.value = "";
        // Display the modal overlay.
        saveModalEl.hidden = false;
        // Focus title input for quick entry.
        if (titleInputEl) titleInputEl.focus();
    };

    // Hide the save modal.
    const hideSaveModal = () => {
        // Guard against missing modal.
        if (!saveModalEl) return;
        // Hide the modal overlay.
        saveModalEl.hidden = true;
    };

    // Determine whether a new note should prompt for save.
    const shouldPromptSave = () => {
        // Only prompt for new notes without IDs.
        if (currentNoteId !== null) return false;
        // Guard against missing editor.
        if (!quill) return false;
        // Require that the user actually typed content.
        if (!hasUserTyped) return false;
        // Check for non-empty editor content.
        const hasContent = quill.getText().trim().length > 0;
        // Prompt only when there is content.
        return hasContent;
    };

    // Render the notes list into the sidebar.
    const renderNotesList = (notes) => {
        // Guard against missing list element.
        if (!listEl) return;
        // Clear existing list content.
        listEl.innerHTML = "";
        // Toggle empty state visibility.
        if (emptyEl) emptyEl.hidden = notes.length > 0;
        // Show or hide clear filter button.
        if (clearFilterBtn) clearFilterBtn.hidden = !activeTagSlug;
        // Show or hide filter label.
        if (filterLabelEl) {
            filterLabelEl.hidden = !activeTagSlug;
            filterLabelEl.textContent = activeTagSlug ? `Filter: #${activeTagSlug}` : "";
        }
        // Build list entries.
        notes.forEach((note) => {
            // Create list item wrapper.
            const item = document.createElement("li");
            // Create clickable note container.
            const button = document.createElement("div");
            // Apply the base item class.
            button.className = "notes-item";
            // Mark the item as active when it matches current note.
            if (currentNoteId === note.id) {
                button.classList.add("is-active");
            }
            // Make the item focusable and clickable.
            button.setAttribute("role", "button");
            // Allow keyboard focus.
            button.setAttribute("tabindex", "0");
            // Store the note id for event handling.
            button.dataset.noteId = String(note.id);
            // Set ARIA label for screen readers.
            button.setAttribute("aria-label", `Open note: ${note.title || "Untitled"}`);
            // Create title element.
            const titleEl = document.createElement("div");
            // Apply title class.
            titleEl.className = "notes-item__title";
            // Set title text.
            titleEl.textContent = note.title || "Untitled";
            // Append title into item.
            button.appendChild(titleEl);
            // Add tag badge when present.
            if (note.tag && note.tag.slug) {
                // Create tag element.
                const tagBtn = document.createElement("button");
                // Apply tag class.
                tagBtn.className = "notes-item__tag";
                // Mark as a button for filtering.
                tagBtn.type = "button";
                // Store tag slug for click handler.
                tagBtn.dataset.tagSlug = note.tag.slug;
                // Set tag label text.
                tagBtn.textContent = note.tag.name || note.tag.slug;
                // Append tag badge to item.
                button.appendChild(tagBtn);
            }
            // Create open indicator.
            const openEl = document.createElement("span");
            // Apply open indicator class.
            openEl.className = "notes-item__open";
            // Set open label.
            openEl.textContent = "Open";
            // Append open label to item.
            button.appendChild(openEl);
            // Append the button into the list item.
            item.appendChild(button);
            // Append the list item into the list.
            listEl.appendChild(item);
        });
    };

    // Fetch notes list from the server.
    const loadNotesList = async (tagSlug) => {
        // Update active tag filter state.
        activeTagSlug = tagSlug || "";
        // Build list URL with optional tag filter.
        const url = activeTagSlug
            ? `${listUrl}?tag=${encodeURIComponent(activeTagSlug)}`
            : listUrl;
        // Guard when list URL is missing.
        if (!url) return;
        // Fetch notes from backend.
        try {
            // Issue GET request to list endpoint.
            const response = await fetch(url, {
                headers: { "X-Requested-With": "XMLHttpRequest" },
                credentials: "same-origin",
            });
            // Parse JSON response.
            const data = await response.json();
            // Render the notes list.
            renderNotesList(Array.isArray(data.notes) ? data.notes : []);
        } catch (error) {
            // Render empty list on failure.
            renderNotesList([]);
        }
    };

    // Load a single note into the editor.
    const loadNote = async (noteId) => {
        // Guard against missing editor.
        if (!quill) return;
        // Build the detail URL.
        const detailUrl = buildDetailUrl(noteId);
        // Fetch the note from backend.
        try {
            // Issue GET request to detail endpoint.
            const response = await fetch(detailUrl, {
                headers: { "X-Requested-With": "XMLHttpRequest" },
                credentials: "same-origin",
            });
            // Parse JSON response.
            const data = await response.json();
            // Extract note object from payload.
            const note = data.note || null;
            // Skip when payload is missing.
            if (!note) return;
            // Set current note ID.
            currentNoteId = note.id;
        // Reset dirty state.
        isDirty = false;
        // Reset typed state for a fresh note.
        hasUserTyped = false;
            // Enable delete button for existing notes.
            if (deleteBtn) deleteBtn.disabled = false;
        // Inject HTML into the editor.
        quill.setText("");
        // Paste HTML content from the note.
        quill.clipboard.dangerouslyPasteHTML(note.content_html || "");
        // Reset typed state because this is a programmatic load.
        hasUserTyped = false;
            // Reload list to highlight active note.
            await loadNotesList(activeTagSlug);
        } catch (error) {
            // Ignore load failures.
        }
    };

    // Apply a selected text color to the editor.
    const applyTextColor = (color, buttonEl) => {
        // Guard against missing editor.
        if (!quill) return;
        // Apply the color format to the editor.
        quill.format("color", color);
        // Update active button state.
        colorButtons.forEach((btn) => {
            btn.classList.toggle("is-active", btn === buttonEl);
        });
        // Refocus the editor for typing.
        quill.focus();
    };

    // Enter a code block at the current cursor position.
    const enterCodeBlock = () => {
        // Guard against missing editor.
        if (!quill) return;
        // Ensure the editor is focused before reading selection.
        quill.focus();
        // Read the current selection (or fall back to the last known one).
        let range = quill.getSelection();
        if (!range && lastSelection) {
            range = { index: lastSelection.index, length: lastSelection.length };
        }
        // When no selection exists, move the cursor to the end.
        if (!range) {
            const length = quill.getLength();
            range = { index: Math.max(0, length - 1), length: 0 };
        }
        // Exit if selection still fails to resolve.
        if (!range) return;
        // Restore the selection so the caret stays visible.
        quill.setSelection(range.index, range.length, "api");
        // Skip if already inside a code block.
        const formats = quill.getFormat(range);
        if (formats["code-block"]) {
            // Keep focus and selection visible when already in code mode.
            quill.focus();
            quill.setSelection(range.index, range.length, "api");
            return;
        }
        // Use a mutable index for inserting a new line.
        let index = range.index;
        // Determine line offset at the cursor.
        const lineInfo = quill.getLine(index);
        const offset = lineInfo ? lineInfo[1] : 0;
        // Insert a newline when not at the line start.
        if (offset !== 0) {
            quill.insertText(index, "\n", "user");
            index += 1;
        }
        // Clear any inline color before entering code block.
        quill.format("color", false);
        // Apply code block formatting on the current line.
        quill.formatLine(index, 1, "code-block", true);
        // Move cursor into the code block.
        quill.setSelection(index, 0, "api");
        // Ensure the editor keeps focus after the shortcut.
        quill.focus();
    };

    // Create the copy icon markup (matches AI response copy button).
    const copyIconMarkup = `
        <span class="llm-copy-btn__icon llm-copy-btn__icon--copy" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="9" y="9" width="11" height="11" rx="2"></rect>
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
          </svg>
        </span>
        <span class="llm-copy-btn__icon llm-copy-btn__icon--check" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.3">
            <path stroke-linecap="round" stroke-linejoin="round" d="M5 12.5l4.2 4.2L19 7.2"></path>
          </svg>
        </span>
    `.trim();

    // Copy text to clipboard with fallback.
    const copyTextToClipboard = async (text) => {
        // Prefer modern clipboard API.
        if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
            await navigator.clipboard.writeText(text);
            return;
        }
        // Fallback to a hidden textarea.
        const helper = document.createElement("textarea");
        helper.value = text;
        helper.setAttribute("readonly", "");
        helper.style.position = "fixed";
        helper.style.top = "-9999px";
        helper.style.left = "-9999px";
        document.body.appendChild(helper);
        helper.focus();
        helper.select();
        const success = document.execCommand("copy");
        helper.remove();
        if (!success) {
            throw new Error("copy-failed");
        }
    };

    // Provide feedback on copy success/failure.
    const setCopyButtonFeedback = (button, copied) => {
        // Guard against missing button.
        if (!button) return;
        // Clear any existing feedback timer.
        if (button._copyFeedbackTimer) {
            window.clearTimeout(button._copyFeedbackTimer);
        }
        // Reset state and apply new status.
        button.classList.remove("is-copied", "is-copy-failed");
        button.classList.add(copied ? "is-copied" : "is-copy-failed");
        // Update labels for accessibility.
        const defaultLabel = button.getAttribute("data-copy-default") || "Copy";
        const copiedLabel = button.getAttribute("data-copy-copied") || "Copied";
        const failedLabel = button.getAttribute("data-copy-failed") || "Copy failed";
        const activeLabel = copied ? copiedLabel : failedLabel;
        button.setAttribute("aria-label", activeLabel);
        button.setAttribute("title", activeLabel);
        // Restore label after a short delay.
        button._copyFeedbackTimer = window.setTimeout(() => {
            button.classList.remove("is-copied", "is-copy-failed");
            button.setAttribute("aria-label", defaultLabel);
            button.setAttribute("title", defaultLabel);
        }, 1200);
    };

    // Ensure the overlay layer exists above the editor.
    const ensureCopyOverlayLayer = () => {
        if (!editorMountEl) return null;
        const wrap = editorMountEl.closest(".notes-editor-wrap") || editorMountEl.parentElement;
        if (!wrap) return null;
        if (!copyOverlayLayer) {
            copyOverlayLayer = document.createElement("div");
            copyOverlayLayer.className = "notes-code-copy-layer";
            wrap.appendChild(copyOverlayLayer);
        }
        return copyOverlayLayer;
    };

    // Update overlay copy buttons without mutating the editor DOM.
    const updateCopyOverlay = () => {
        if (!quill) return;
        const layer = ensureCopyOverlayLayer();
        if (!layer) return;
        // Clear existing overlay buttons.
        layer.innerHTML = "";
        // Locate code blocks inside the editor.
        const codeBlocks = Array.from(quill.root.querySelectorAll("pre.ql-syntax"));
        if (codeBlocks.length === 0) return;
        const layerRect = layer.getBoundingClientRect();
        codeBlocks.forEach((codeEl) => {
            const codeRect = codeEl.getBoundingClientRect();
            // Skip blocks outside the visible area.
            if (codeRect.bottom < layerRect.top || codeRect.top > layerRect.bottom) return;
            // Create an overlay button positioned above the code block.
            const copyBtn = document.createElement("button");
            copyBtn.type = "button";
            copyBtn.className = "notes-copy-code llm-copy-btn";
            copyBtn.innerHTML = copyIconMarkup;
            copyBtn.setAttribute("aria-label", "Copy code");
            copyBtn.setAttribute("title", "Copy code");
            copyBtn.setAttribute("data-copy-default", "Copy code");
            copyBtn.setAttribute("data-copy-copied", "Copied");
            copyBtn.setAttribute("data-copy-failed", "Copy failed");
            copyBtn.style.position = "absolute";
            copyBtn.style.top = `${Math.max(0, codeRect.top - layerRect.top) + 8}px`;
            copyBtn.style.left = `${Math.max(0, codeRect.right - layerRect.left) - 8}px`;
            copyBtn.style.transform = "translate(-100%, 0)";
            // Attach copy handler.
            copyBtn.addEventListener("click", async function () {
                const textToCopy = (codeEl.textContent || "").trim();
                if (!textToCopy) return;
                try {
                    await copyTextToClipboard(textToCopy);
                    setCopyButtonFeedback(copyBtn, true);
                } catch (error) {
                    setCopyButtonFeedback(copyBtn, false);
                }
            });
            layer.appendChild(copyBtn);
        });
    };

    // Schedule a safe overlay refresh.
    const scheduleCopyOverlayUpdate = () => {
        if (copyOverlayRaf) return;
        copyOverlayRaf = window.requestAnimationFrame(() => {
            copyOverlayRaf = null;
            updateCopyOverlay();
        });
    };

    // Create a new note on the server.
    const createNote = async (title, tagText) => {
        // Guard against missing editor.
        if (!quill) return null;
        // Build payload for creation.
        const payload = {
            title: title,
            tag: tagText,
            content_html: quill.root.innerHTML || "",
        };
        // Send POST request to list endpoint.
        try {
            // Issue POST request with JSON payload.
            const response = await fetch(listUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie("csrftoken"),
                    "X-Requested-With": "XMLHttpRequest",
                },
                credentials: "same-origin",
                body: JSON.stringify(payload),
            });
            // Parse response JSON.
            const data = await response.json();
            // Return created note payload when successful.
            return data.note || null;
        } catch (error) {
            // Return null on failure.
            return null;
        }
    };

    // Save changes for an existing note (autosave).
    const updateNote = async () => {
        // Guard against missing note ID.
        if (!currentNoteId) return;
        // Guard against missing editor.
        if (!quill) return;
        // Build detail URL for update.
        const detailUrl = buildDetailUrl(currentNoteId);
        // Build update payload.
        const payload = {
            content_html: quill.root.innerHTML || "",
        };
        // Send POST request to update endpoint.
        try {
            // Issue POST request with JSON payload.
            await fetch(detailUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie("csrftoken"),
                    "X-Requested-With": "XMLHttpRequest",
                },
                credentials: "same-origin",
                body: JSON.stringify(payload),
            });
            // Clear dirty state after save.
            isDirty = false;
        } catch (error) {
            // Keep dirty state on failure.
        }
    };

    // Schedule autosave with debounce.
    const scheduleAutosave = () => {
        // Only autosave existing notes.
        if (!currentNoteId) return;
        // Clear any existing debounce timer.
        if (autosaveTimer) window.clearTimeout(autosaveTimer);
        // Set new debounce timer.
        autosaveTimer = window.setTimeout(() => {
            // Clear timer reference.
            autosaveTimer = null;
            // Trigger update on debounce.
            updateNote();
        }, 1200);
    };

    // Delete the current note.
    const deleteCurrentNote = async () => {
        // Guard against missing note ID.
        if (!currentNoteId) return;
        // Build detail URL for deletion.
        const detailUrl = buildDetailUrl(currentNoteId);
        // Send DELETE request.
        try {
            // Issue DELETE request to backend.
            await fetch(detailUrl, {
                method: "DELETE",
                headers: {
                    "X-CSRFToken": getCookie("csrftoken"),
                    "X-Requested-With": "XMLHttpRequest",
                },
                credentials: "same-origin",
            });
            // Reset editor after delete.
            resetEditor();
            // Refresh the notes list.
            await loadNotesList(activeTagSlug);
        } catch (error) {
            // Ignore delete failures for now.
        }
    };

    // Initialize the Quill editor.
    const initQuill = () => {
        // Guard against missing mount element.
        if (!editorMountEl) return;
        // Guard against missing Quill dependency.
        if (!window.Quill) return;
        // Create a new Quill instance with custom shortcuts.
        quill = new window.Quill(editorMountEl, {
            theme: "snow",
            modules: {
                toolbar: false,
                // Enable syntax highlighting for code blocks.
                syntax: true,
                keyboard: {
                    bindings: {
                        heading1: {
                            key: "1",
                            shortKey: true,
                            handler: function (range) {
                                if (shortcutsDisabled()) return true;
                                this.quill.formatLine(range.index, range.length, "header", 1);
                                return false;
                            },
                        },
                        heading2: {
                            key: "2",
                            shortKey: true,
                            handler: function (range) {
                                if (shortcutsDisabled()) return true;
                                this.quill.formatLine(range.index, range.length, "header", 2);
                                return false;
                            },
                        },
                        paragraph: {
                            key: "P",
                            altKey: true,
                            handler: function () {
                                if (shortcutsDisabled()) return true;
                                this.quill.format("header", false);
                                this.quill.format("code-block", false);
                                this.quill.format("blockquote", false);
                                this.quill.format("list", false);
                                this.quill.format("code", false);
                                return false;
                            },
                        },
                        bold: {
                            key: "B",
                            shortKey: true,
                            handler: function (range, context) {
                                if (shortcutsDisabled()) return true;
                                this.quill.format("bold", !context.format.bold);
                                return false;
                            },
                        },
                        codeBlock: {
                            key: "X",
                            // shortKey: true,
                            shiftKey: true,
                            handler: function (range, context) {
                                // Skip shortcut handling on mobile.
                                if (shortcutsDisabled()) return true;
                                // Enter a code block at the cursor.
                                enterCodeBlock();
                                return false;
                            },
                        },
                        exitCodeBlock: {
                            key: "Enter",
                            shiftKey: true,
                            handler: function (range, context) {
                                // Skip shortcut handling on mobile.
                                if (shortcutsDisabled()) return true;
                                // Only handle exit when currently in a code block.
                                if (!context.format["code-block"]) return true;
                                // Insert a newline.
                                this.quill.insertText(range.index, "\n", "user");
                                // Remove code block formatting on the next line.
                                this.quill.formatLine(range.index + 1, 1, "code-block", false);
                                // Move cursor to the new normal line.
                                this.quill.setSelection(range.index + 1, 0, "silent");
                                return false;
                            },
                        },
                    },
                },
            },
            placeholder: "Start typing your notes here...",
        });
        // Enable spellcheck for writing notes.
        quill.root.setAttribute("spellcheck", "true");
        // Listen for editor changes to set dirty state and autosave.
        quill.on("text-change", function (delta, oldDelta, source) {
            // Only mark dirty when the user edits directly.
            if (source === "user") {
                // Mark the editor as dirty on change.
                isDirty = true;
                // Mark that the user has typed content.
                hasUserTyped = true;
                // Schedule autosave for existing notes.
                scheduleAutosave();
            }
            // Refresh overlay copy buttons after changes.
            scheduleCopyOverlayUpdate();
        });
        // Track the last known selection so shortcuts can restore focus.
        quill.on("selection-change", function (range) {
            if (range) {
                lastSelection = { index: range.index, length: range.length };
            }
        });
        // Keep overlay buttons aligned while scrolling inside the editor.
        quill.root.addEventListener("scroll", scheduleCopyOverlayUpdate, { passive: true });
        // Update overlay on window resize.
        window.addEventListener("resize", scheduleCopyOverlayUpdate);
        // Ensure overlay is attached on init.
        scheduleCopyOverlayUpdate();
    };

    // Handle opening the notes panel.
    const handleOpen = () => {
        // Open the panel UI.
        setPanelOpen(true);
        // Hide any lingering save modal.
        hideSaveModal();
        // Ensure sidebar starts closed by default.
        setSidebarOpen(false);
        // Reset editor to a blank note.
        resetEditor();
        // Load the notes list for sidebar.
        loadNotesList(activeTagSlug);
    };

    // Toggle the notes panel open/close (Alt+N shortcut).
    const toggleNotesPanel = () => {
        // Check current open state.
        const isOpen = bodyEl.classList.contains("notes-open");
        // Close when open, otherwise open.
        if (isOpen) {
            handleClose();
        } else {
            handleOpen();
        }
    };

    // Handle closing the notes panel.
    const handleClose = () => {
        // Prompt for save when a new note has content.
        if (shouldPromptSave()) {
            showSaveModal();
            return;
        }
        // Close the panel immediately.
        setPanelOpen(false);
    };

    // Handle save from the modal.
    const handleSave = async () => {
        // Guard against missing inputs.
        if (!titleInputEl) return;
        // Read title input.
        const title = titleInputEl.value.trim();
        // Validate title input.
        if (!title) {
            if (saveErrorEl) {
                saveErrorEl.textContent = "Title is required.";
                saveErrorEl.hidden = false;
            }
            return;
        }
        // Read tag input.
        const tagText = tagInputEl ? tagInputEl.value.trim() : "";
        // Create the note in the backend.
        const createdNote = await createNote(title, tagText);
        // Handle creation failure.
        if (!createdNote) {
            if (saveErrorEl) {
                saveErrorEl.textContent = "Save failed. Try again.";
                saveErrorEl.hidden = false;
            }
            return;
        }
        // Hide the save modal.
        hideSaveModal();
        // Reset editor after saving.
        resetEditor();
        // Refresh the list to include the new note.
        await loadNotesList(activeTagSlug);
        // Close panel after saving per requirement.
        setPanelOpen(false);
        // Clear pending close flag.
    };

    // Handle exit from the modal (discard).
    const handleExit = () => {
        // Hide the modal overlay.
        hideSaveModal();
        // Reset editor state.
        resetEditor();
        // Close panel after discard.
        setPanelOpen(false);
        // Clear pending close flag.
    };

    // Handle clicks inside the notes list.
    const handleListClick = (event) => {
        // Identify tag button clicks.
        const tagBtn = event.target.closest("[data-tag-slug]");
        // Apply tag filter when tag clicked.
        if (tagBtn) {
            event.preventDefault();
            loadNotesList(tagBtn.dataset.tagSlug || "");
            return;
        }
        // Identify note item clicks.
        const noteEl = event.target.closest("[data-note-id]");
        // Exit when no note element is clicked.
        if (!noteEl) return;
        // Prevent default behavior.
        event.preventDefault();
        // Extract note ID.
        const noteId = Number(noteEl.dataset.noteId || 0);
        // Ignore invalid IDs.
        if (!noteId) return;
        // If there is an unsaved new note, prompt before switching.
        if (shouldPromptSave()) {
            showSaveModal();
            return;
        }
        // Load the selected note into the editor.
        loadNote(noteId);
    };

    // Handle keyboard activation for note items.
    const handleListKeydown = (event) => {
        // Only handle Enter or Space.
        if (event.key !== "Enter" && event.key !== " ") return;
        // Ignore key events coming from tag buttons.
        if (event.target.closest("[data-tag-slug]")) return;
        // Identify note item.
        const noteEl = event.target.closest("[data-note-id]");
        // Exit when not on a note element.
        if (!noteEl) return;
        // Prevent default scroll for spacebar.
        event.preventDefault();
        // Trigger click handler.
        noteEl.click();
    };

    // Initialize Quill editor.
    initQuill();

    // Attach open button handler.
    if (openBtn) openBtn.addEventListener("click", handleOpen);
    // Attach close button handler.
    if (closeBtn) closeBtn.addEventListener("click", handleClose);
    // Do not close on backdrop click (close only via Close button).
    // Attach delete button handler.
    if (deleteBtn) deleteBtn.addEventListener("click", deleteCurrentNote);
    // Attach sidebar toggle handler.
    if (sidebarToggleBtn) {
        sidebarToggleBtn.addEventListener("click", function () {
            setSidebarOpen(!panelEl.classList.contains("notes-sidebar-open"));
        });
    }
    // Attach clear filter handler.
    if (clearFilterBtn) {
        clearFilterBtn.addEventListener("click", function () {
            loadNotesList("");
        });
    }
    // Attach list click handler.
    if (listEl) listEl.addEventListener("click", handleListClick);
    // Attach list keydown handler for accessibility.
    if (listEl) listEl.addEventListener("keydown", handleListKeydown);
    // Attach save modal save handler.
    if (saveBtn) saveBtn.addEventListener("click", handleSave);
    // Attach save modal exit handler.
    if (exitBtn) exitBtn.addEventListener("click", handleExit);
    // Attach color button handlers for text color.
    colorButtons.forEach((buttonEl) => {
        buttonEl.addEventListener("click", function () {
            // Read the color value from the data attribute.
            const colorValue = buttonEl.dataset.notesColor || "";
            // Skip when no color is provided.
            if (!colorValue) return;
            // Apply the selected color to the editor.
            applyTextColor(colorValue, buttonEl);
        });
    });
    // Close modal on Escape key.
    document.addEventListener("keydown", function (event) {
        if (event.key !== "Escape") return;
        if (!saveModalEl || saveModalEl.hidden) return;
        event.preventDefault();
        handleExit();
    });

    // Toggle notes panel with Alt+N.
    document.addEventListener("keydown", function (event) {
        // Use Alt+N without Ctrl/Shift/Meta.
        const isAltN = event.altKey
            && !event.ctrlKey
            && !event.shiftKey
            && !event.metaKey
            && String(event.key).toLowerCase() === "n";
        // Ignore non-matching keys.
        if (!isAltN) return;
        // Prevent browser default behavior.
        event.preventDefault();
        // Toggle the notes panel.
        toggleNotesPanel();
    });
});
