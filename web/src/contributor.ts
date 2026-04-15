import './style.css';
import $ from 'jquery';
import {
    getToken, clearToken, getMe, logout,
    translate, verify, createSuggestion, getSuggestions,
    User, Suggestion,
} from './api';

let currentUser: User | null = null;

// Last set of API translation results
type ApiResult = { api: string; translation: string | null; error: string | null };
let lastResults: ApiResult[] = [];
// Index into lastResults for the selected translation
let selectedIdx = 0;

$(async () => {
    if (!getToken()) { window.location.href = '/'; return; }

    try {
        currentUser = await getMe();
        if (currentUser.role !== 'contributor') {
            window.location.href = '/reviewer.html';
            return;
        }
    } catch {
        clearToken();
        window.location.href = '/';
        return;
    }

    $('#ann-info').text(`${currentUser.username} · Contributor`);
    renderStats(currentUser.quota_remaining, currentUser.daily_quota, currentUser.total_points);
    loadMyContributions();


    // Auto-translate
    $('#tr-btn').on('click', async () => {
        const text = String($('#src-text').val() ?? '').trim();
        if (!text) { alert('Enter source text first.'); return; }
        $('#tr-btn').prop('disabled', true);
        $('#tr-status').text('Translating…');
        try {
            const data = await translate(
                text,
                String($('#src-lang').val()),
                String($('#tgt-lang').val()),
            );
            lastResults = data.results;
            selectedIdx = data.results.findIndex(r => r.translation !== null);
            if (selectedIdx < 0) selectedIdx = 0;
            currentUser!.quota_remaining = data.quota_remaining;
            renderStats(data.quota_remaining, currentUser!.daily_quota, currentUser!.total_points);
            renderApiResults();
            $('#pass-count').text('');
            $('#verify-result').text('');
            $('#tr-status').text('✓ Done');
        } catch (err) {
            $('#tr-status').text(`✗ ${err}`);
        } finally {
            $('#tr-btn').prop('disabled', false);
        }
    });

    // Select translation radio (event delegation)
    $('#api-results-body').on('change', 'input[name=tr-select]', function () {
        selectedIdx = parseInt(String($(this).val()));
    });

    // Test verification (on all translations)
    $('#verify-btn').on('click', async () => {
        const translations = lastResults.map(r => r.translation).filter(t => t !== null) as string[];
        const vcontent = String($('#vc-content').val() ?? '').trim();
        if (translations.length === 0) { $('#verify-result').html('<span class="msg-err">No translations available</span>'); return; }
        if (!vcontent) { $('#verify-result').html('<span class="msg-err">No verification content</span>'); return; }

        $('#verify-result').html('<span style="color:#64748b;font-size:0.9em">Verifying...</span>');
        try {
            const data = await verify(translations, vcontent);

            let resultIdx = 0;
            let pass = 0;
            lastResults.forEach((r, i) => {
                if (r.translation !== null) {
                    const verified = data.results[resultIdx++];
                    const badge = verified ? '<span class="vpill vpill-pass">✓</span>' : '<span class="vpill vpill-fail">✗</span>';
                    $(`[data-idx="${i}"]`).html(badge);
                    if (verified) pass++;
                } else {
                    $(`[data-idx="${i}"]`).html('');
                }
            });
            const cls = pass === 0 ? 'count-fail' : (pass === translations.length ? 'count-pass' : 'count-partial');
            $('#verify-result').html("");
            $('#pass-count').html(`<span class="${cls}">${pass}/${translations.length} pass verification</span>`);
        } catch (err) {
            $('#verify-result').html(`<span class="msg-err">${escHtml(String(err))}</span>`);
        }
    });

    // Submit suggestion
    $('#submit-btn').on('click', async () => {
        const source_text = String($('#src-text').val() ?? '').trim();
        const translation = getSelectedTranslation();
        const source_lang = String($('#src-lang').val());
        const target_lang = String($('#tgt-lang').val());
        const verification_content = String($('#vc-content').val() ?? '').trim();

        if (!source_text || !translation || !verification_content) {
            $('#submit-status').html('<span class="msg-err">Please fill all required fields and translate first</span>');
            return;
        }
        try {
            await createSuggestion({
                source_text, translation, source_lang, target_lang,
                verification_content,
            });
            $('#submit-status').html('<span class="msg-ok">✓ Submitted!</span>');
            $('#src-text, #vc-content').val('');
            $('#verify-result').html('');
            lastResults = [];
            $('#api-results').hide();
            loadMyContributions();
            setTimeout(() => $('#submit-status').html(''), 3000);
        } catch (err) {
            $('#submit-status').html(`<span class="msg-err">${escHtml(String(err))}</span>`);
        }
    });

    // Logout
    $('#logout-btn').on('click', async () => {
        try { await logout(); } finally { clearToken(); window.location.href = '/'; }
    });
});

// ---- Stats bar ----

function renderStats(remaining: number, total: number, points: number): void {
    const pct = total > 0 ? (remaining / total * 100) : 0;
    $('#quota-fill').css('width', `${pct}%`);
    $('#quota-text').text(`${remaining} / ${total} remaining`);
    $('#total-points').text(String(points));
}

// ---- API results table ----

function renderApiResults(): void {
    const $body = $('#api-results-body');
    $body.html(lastResults.map((r, i) => {
        const isSelected = i === selectedIdx;
        const trText = r.translation ?? `<em class="tr-error">${escHtml(r.error ?? 'Error')}</em>`;
        const verifyBadge = '';
        return `<div class="api-result-row">
          <label class="api-radio">
            <input type="radio" name="tr-select" value="${i}"${isSelected ? ' checked' : ''}${r.translation === null ? ' disabled' : ''}>
            <span class="api-name">${escHtml(r.api)}</span>
          </label>
          <div class="tr-display">${trText}</div>
          <span class="verify-pill" data-idx="${i}">${verifyBadge}</span>
        </div>`;
    }).join(''));
    $('#api-results').show();
}



function getSelectedTranslation(): string {
    const r = lastResults[selectedIdx];
    return r?.translation ?? '';
}

// ---- Sidebar: my submissions ----

async function loadMyContributions(): Promise<void> {
    try {
        const sugs = await getSuggestions();
        const $el = $('#my-list');
        if (!sugs.length) { $el.html('<div class="empty">No submissions yet</div>'); return; }
        $el.html(sugs.map(renderMySug).join(''));
    } catch { /* ignore */ }
}

function renderMySug(s: Suggestion): string {
    const srcPreview = s.source_text.length > 60 ? s.source_text.slice(0, 60) + '…' : s.source_text;
    return `<div class="sug-mini">
        <div class="sug-mini-meta">#${s.id} &middot; ${s.source_lang}&rarr;${s.target_lang} &middot; ${fmtDate(s.created_at)}</div>
        <div class="sug-mini-text">${escHtml(srcPreview)}</div>
        <div class="sug-mini-tr">${escHtml(s.translation)}</div>
        <div class="sug-mini-footer">
          <code class="sug-mini-vc">${escHtml(s.verification_content)}</code>
          ${scoreBadge(s.points)}
        </div>
    </div>`;
}

function escHtml(str: string): string { return $('<div>').text(str).html(); }

function fmtDate(dt: string): string { return (dt ?? '').replace('T', ' ').slice(0, 16); }

function scoreBadge(p: number): string {
    if (p < 0) return '<span class="badge badge-pending">Pending</span>';
    const labels = ['0 · Rejected', '1 · Good', '2 · Excellent'];
    return `<span class="badge badge-score-${p}">${labels[p]}</span>`;
}
