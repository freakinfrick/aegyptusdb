/* ═══════════════════════════════════════════════════════════════════════════
 * web/reader.js — EB-Garamond article-reader overlay (window.Reader).
 * ─────────────────────────────────────────────────────────────────────────
 * Day-2 carry-over, §9 project-spec.md. Full-screen overlay over the game
 * canvas with:
 *   • EB Garamond serif body
 *   • inline hieroglyph spans (with latin-transliteration fallback when
 *     G.hieroFallback is true — we never render tofu)
 *   • [▶ HEAR IT]         — triggers Edge TTS via /hackathon/tts
 *   • [✦ SPEAK ABOUT THIS] — opens Oracle chat with "speak about [theme]"
 *   • ESC or [×] to close
 *
 * Injected lazily: first call to Reader.open(article) builds the DOM.
 * Called from:
 *   - game.js handleOracleEvent when tool=read_article lands
 *   - game.js interact() on golden tablets (future: Sanctum horseshoe)
 * ═════════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';
  if (window.Reader) return;

  const CSS = `
#reader-overlay {
  position: fixed; inset: 0; z-index: 60;
  display: none;
  background: rgba(6, 5, 4, 0.985);
  color: #e8dcc8;
  font-family: 'EB Garamond', 'Garamond', serif;
  font-size: 18px; line-height: 1.82;
  flex-direction: column;
}
#reader-overlay.active { display: flex; }

#reader-header {
  padding: 14px 32px;
  border-bottom: 1px solid #2a2420;
  display: flex; align-items: center; justify-content: space-between;
  flex-shrink: 0;
  font-family: 'Fira Code', monospace;
}
#reader-header .r-title {
  color: #c4922a; font-size: 13px; letter-spacing: 2px;
  text-transform: uppercase;
}
#reader-header .r-sub {
  color: #7a6040; font-size: 11px; margin-left: 16px; letter-spacing: 1px;
}
#reader-header .r-close {
  background: none; border: 1px solid #2a2420; color: #8a8070;
  font-family: 'Fira Code', monospace; font-size: 11px;
  padding: 3px 12px; cursor: pointer;
}
#reader-header .r-close:hover { border-color: #a04030; color: #a04030; }

#reader-body {
  flex: 1; overflow-y: auto;
  padding: 36px clamp(36px, 8vw, 160px);
  max-width: 880px; margin: 0 auto; width: 100%;
  box-sizing: border-box;
}
#reader-body h1 {
  font-family: 'Fira Code', monospace; font-size: 15px;
  color: #c4922a; letter-spacing: 3px; text-transform: uppercase;
  border-bottom: 1px solid #3a2e24; padding-bottom: 12px; margin-bottom: 24px;
}
#reader-body h2 {
  font-family: 'Fira Code', monospace; font-size: 13px;
  color: #9a78aa; letter-spacing: 2px; margin: 28px 0 12px;
}
#reader-body p { margin-bottom: 16px; }
#reader-body blockquote {
  border-left: 2px solid #8a6a1e; padding: 6px 20px; margin: 18px 4px;
  color: #d8ccb8; font-style: italic;
}
#reader-body .hiero {
  font-family: 'Noto Egyptian', serif;
  color: #c4922a; font-size: 1.15em;
}
#reader-body .hiero.fallback {
  font-family: 'EB Garamond', serif; font-style: italic;
  color: #c4922a;
}
#reader-body .cite {
  font-family: 'Fira Code', monospace; font-size: 11px;
  color: #7a6040; margin: -8px 0 16px 4px;
}
#reader-body .lede {
  color: #b49878; font-style: italic; margin-bottom: 24px;
}

#reader-footer {
  padding: 14px 32px;
  border-top: 1px solid #2a2420;
  display: flex; gap: 16px; align-items: center;
  flex-shrink: 0;
  font-family: 'Fira Code', monospace; font-size: 12px;
}
#reader-footer button {
  background: rgba(30, 24, 18, 0.8);
  border: 1px solid #5a4838; color: #c4922a;
  font-family: 'Fira Code', monospace; font-size: 12px;
  padding: 6px 14px; letter-spacing: 1px; cursor: pointer;
}
#reader-footer button:hover { border-color: #c4922a; background: rgba(60, 46, 30, 0.9); }
#reader-footer button[disabled] { opacity: 0.45; cursor: default; }
#reader-footer .r-status { margin-left: auto; color: #6a5840; }
#reader-footer audio { display: none; }
#reader-footer .r-hear-playing { color: #8fbc9f; border-color: #8fbc9f; }
  `;

  function injectCSS() {
    if (document.getElementById('reader-overlay-style')) return;
    const s = document.createElement('style');
    s.id = 'reader-overlay-style';
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  function buildDOM() {
    if (document.getElementById('reader-overlay')) return;
    const root = document.createElement('div');
    root.id = 'reader-overlay';
    root.innerHTML = `
      <div id="reader-header">
        <div>
          <span class="r-title" id="reader-title">TABLET</span>
          <span class="r-sub" id="reader-sub"></span>
        </div>
        <button class="r-close" id="reader-close" aria-label="Close">[ ESC ]</button>
      </div>
      <div id="reader-body"></div>
      <div id="reader-footer">
        <button id="reader-hear">[ \u25b6 HEAR IT ]</button>
        <button id="reader-speak">[ \u2726 SPEAK ABOUT THIS ]</button>
        <span class="r-status" id="reader-status"></span>
        <audio id="reader-audio" preload="none"></audio>
      </div>
    `;
    document.body.appendChild(root);

    document.getElementById('reader-close').addEventListener('click', Reader.close);
    document.getElementById('reader-hear').addEventListener('click', onHearIt);
    document.getElementById('reader-speak').addEventListener('click', onSpeakAbout);
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && document.getElementById('reader-overlay').classList.contains('active')) {
        e.preventDefault();
        Reader.close();
      }
    });

    const audio = document.getElementById('reader-audio');
    audio.addEventListener('ended', () => {
      document.getElementById('reader-hear').classList.remove('r-hear-playing');
      document.getElementById('reader-status').textContent = '';
    });
  }

  function esc(s) {
    return String(s || '').replace(/[&<>"']/g, c => ({
      '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'
    }[c]));
  }

  // Detect Egyptian hieroglyph runs (U+13000..U+1343F) and wrap them.
  // Under G.hieroFallback, substitute a latin transliteration span so we
  // never render tofu. The transliteration is passed in via article.hiero_fallback
  // (same shape as §8.3 in project-spec.md); if absent, we dim to ···.
  const HIERO_RE = /[\u{13000}-\u{1343F}]+/gu;
  function renderBodyInline(text, fallbackMap) {
    const useFallback = window.G && window.G.hieroFallback === true;
    return esc(text).replace(HIERO_RE, (match) => {
      if (!useFallback) {
        return `<span class="hiero">${match}</span>`;
      }
      const tr = (fallbackMap && fallbackMap[match]) || '···';
      return `<span class="hiero fallback" title="${esc(match)}">${esc(tr)}</span>`;
    });
  }

  function renderMarkdownIsh(body, fallbackMap) {
    // Minimal markdown: H1/H2, blockquote, paragraph. Inline: **bold**, *italic*.
    const lines = String(body || '').split('\n');
    const out = [];
    let inPara = false;
    const flushPara = () => { if (inPara) { out.push('</p>'); inPara = false; } };
    for (const raw of lines) {
      const line = raw.trimEnd();
      if (!line.trim()) { flushPara(); continue; }
      if (line.startsWith('# ')) {
        flushPara();
        out.push(`<h1>${renderBodyInline(line.slice(2), fallbackMap)}</h1>`);
      } else if (line.startsWith('## ')) {
        flushPara();
        out.push(`<h2>${renderBodyInline(line.slice(3), fallbackMap)}</h2>`);
      } else if (line.startsWith('> ')) {
        flushPara();
        out.push(`<blockquote>${renderBodyInline(line.slice(2), fallbackMap)}</blockquote>`);
      } else if (/^\s*—\s/.test(line) || /^\s*\u2014\s/.test(line)) {
        flushPara();
        out.push(`<p class="cite">${renderBodyInline(line.trim(), fallbackMap)}</p>`);
      } else {
        if (!inPara) { out.push('<p>'); inPara = true; }
        let html = renderBodyInline(line, fallbackMap);
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
                   .replace(/\*(.+?)\*/g, '<em>$1</em>');
        out.push(html + ' ');
      }
    }
    flushPara();
    return out.join('\n');
  }

  function onHearIt() {
    const btn = document.getElementById('reader-hear');
    const audio = document.getElementById('reader-audio');
    if (btn.classList.contains('r-hear-playing')) {
      // Toggle stop
      try { audio.pause(); audio.currentTime = 0; } catch {}
      btn.classList.remove('r-hear-playing');
      document.getElementById('reader-status').textContent = '';
      return;
    }
    const article = Reader._current;
    if (!article) return;
    const status = document.getElementById('reader-status');
    status.textContent = 'Summoning voice…';
    btn.disabled = true;
    // Strip markdown for TTS
    const speechText = stripMdForSpeech(article.body || '');
    fetch('/hackathon/tts', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: speechText.slice(0, 3500),
        voice: 'scribe',
      }),
    }).then(r => r.ok ? r.json() : Promise.reject(r.statusText))
      .then(res => {
        btn.disabled = false;
        if (!res.url) throw new Error(res.error || 'no audio url');
        audio.src = res.url;
        audio.play().then(() => {
          btn.classList.add('r-hear-playing');
          status.textContent = 'Playing…';
        }).catch(e => { status.textContent = 'Play failed: ' + e.message; });
      }).catch(err => {
        btn.disabled = false;
        status.textContent = 'TTS failed: ' + err;
      });
  }

  function onSpeakAbout() {
    const article = Reader._current;
    if (!article) return;
    const theme = article.theme || article.name || 'this article';
    const prompt = `Speak about ${theme}.`;
    Reader.close();
    // Open Oracle chat and inject the prompt.
    if (typeof window.openOracleChat === 'function') {
      window.openOracleChat();
    } else if (window.G) {
      window.G.oracleChatActive = true;
      if (window.G.inputEl) window.G.inputEl.focus();
    }
    // Defer the send so the chat overlay has time to mount.
    setTimeout(() => {
      if (window.G && window.G.inputEl) {
        window.G.inputEl.value = prompt;
        window.G.oracleChatInput = prompt;
        if (typeof window.sendOracleMsg === 'function') window.sendOracleMsg();
      }
    }, 300);
  }

  function stripMdForSpeech(text) {
    return String(text || '')
      .replace(/```[\s\S]*?```/g, ' ')
      .replace(/\[(.+?)\]\(.+?\)/g, '$1')
      .replace(/https?:\/\/\S+/g, '')
      .replace(/\*\*(.+?)\*\*/g, '$1')
      .replace(/\*(.+?)\*/g, '$1')
      .replace(/`(.+?)`/g, '$1')
      .replace(/^#+\s*/gm, '')
      .replace(/^>\s*/gm, '')
      .replace(/\n{3,}/g, '\n\n')
      .trim();
  }

  const Reader = {
    _current: null,

    open(article) {
      if (!article) return;
      injectCSS(); buildDOM();
      Reader._current = article;
      document.getElementById('reader-title').textContent =
        (article.theme || article.name || 'Tablet').toString().toUpperCase();
      const sub = [
        article.period ? `${article.period}` : '',
        article.article_id ? `Tablet ${article.article_id}/9` : '',
        article.canonical_id || '',
      ].filter(Boolean).join(' · ');
      document.getElementById('reader-sub').textContent = sub;
      const body = article.body || article.preview || '';
      const fallbackMap = article.hiero_fallback || null;
      document.getElementById('reader-body').innerHTML =
        renderMarkdownIsh(body, fallbackMap);
      document.getElementById('reader-status').textContent = '';
      document.getElementById('reader-hear').classList.remove('r-hear-playing');
      document.getElementById('reader-overlay').classList.add('active');
    },

    close() {
      const el = document.getElementById('reader-overlay');
      if (el) el.classList.remove('active');
      const audio = document.getElementById('reader-audio');
      if (audio) { try { audio.pause(); audio.currentTime = 0; } catch {} }
      const btn = document.getElementById('reader-hear');
      if (btn) btn.classList.remove('r-hear-playing');
      Reader._current = null;
    },

    isOpen() {
      const el = document.getElementById('reader-overlay');
      return !!(el && el.classList.contains('active'));
    },
  };

  window.Reader = Reader;
})();
