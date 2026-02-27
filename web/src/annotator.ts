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
        if (currentUser.role !== 'annotator') {
            window.location.href = '/senior.html';
            return;
        }
    } catch {
        clearToken();
        window.location.href = '/';
        return;
    }

    $('#ann-info').text(`${currentUser.username} · Annotator`);
    renderStats(currentUser.quota_remaining, currentUser.daily_quota, currentUser.total_points);
    loadMySuggestions();

    // Verification type toggle
    $('input[name=vtype]').on('change', function () {
        const isLlm = $(this).val() === 'llm';
        if (isLlm) {
            $('#vc-label').html('LLM prompt <span class="hint">(used to verify the translation)</span>');
            $('#vc-content').attr('placeholder', 'e.g. Does the translation preserve the pun from the source text?');
            $('#polarity-row').hide();
        } else {
            $('#vc-label').html('Regex pattern <span class="hint">(matched against translation)</span>');
            $('#vc-content').attr('placeholder', 'e.g. \\bword\\b');
            $('#polarity-row').show();
        }
        // Re-compute inline verification whenever type/polarity changes
        recomputeInlineVerification();
    });

    // Polarity toggle — re-compute inline verification
    $('input[name=polarity]').on('change', recomputeInlineVerification);

    // Regex content change — re-compute inline verification live
    $('#vc-content').on('input', recomputeInlineVerification);

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

    // Test verification (on the currently selected translation)
    $('#verify-btn').on('click', async () => {
        const translation = getSelectedTranslation();
        const vtype       = String($('input[name=vtype]:checked').val());
        const vcontent    = String($('#vc-content').val() ?? '').trim();
        if (!translation) { $('#verify-result').html('<span class="msg-err">No translation selected</span>'); return; }
        if (!vcontent)    { $('#verify-result').html('<span class="msg-err">No verification content</span>'); return; }
        const polarity = String($('input[name=polarity]:checked').val() || 'positive');
        try {
            const data = await verify(translation, vtype, vcontent, polarity);
            const cls  = data.verified ? 'msg-ok' : 'msg-err';
            const icon = data.verified ? '✓' : '✗';
            $('#verify-result').html(`<span class="${cls}">${icon} ${escHtml(data.detail)}</span>`);
        } catch (err) {
            $('#verify-result').html(`<span class="msg-err">${escHtml(String(err))}</span>`);
        }
    });

    // Submit suggestion
    $('#submit-btn').on('click', async () => {
        const source_text          = String($('#src-text').val() ?? '').trim();
        const translation          = getSelectedTranslation();
        const source_lang          = String($('#src-lang').val());
        const target_lang          = String($('#tgt-lang').val());
        const verification_type    = String($('input[name=vtype]:checked').val());
        const verification_content = String($('#vc-content').val() ?? '').trim();
        const verification_polarity = String($('input[name=polarity]:checked').val() || 'positive');

        if (!source_text || !translation || !verification_content) {
            $('#submit-status').html('<span class="msg-err">Please fill all required fields and translate first</span>');
            return;
        }
        try {
            await createSuggestion({
                source_text, translation, source_lang, target_lang,
                verification_type, verification_content, verification_polarity,
            });
            $('#submit-status').html('<span class="msg-ok">✓ Submitted!</span>');
            $('#src-text, #vc-content').val('');
            $('#verify-result').html('');
            lastResults = [];
            $('#api-results').hide();
            loadMySuggestions();
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
        const verifyBadge = computeVerifyBadge(r.translation);
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
    updatePassCount();
}

function computeVerifyBadge(translation: string | null): string {
    if (translation === null) return '';
    const vtype   = String($('input[name=vtype]:checked').val());
    const vcontent = String($('#vc-content').val() ?? '').trim();
    if (!vcontent || vtype !== 'regex') return '';
    try {
        const polarity = String($('input[name=polarity]:checked').val() || 'positive');
        const matched  = new RegExp(vcontent, 'i').test(translation);
        const passes   = polarity === 'negative' ? !matched : matched;
        return passes
            ? '<span class="vpill vpill-pass">✓</span>'
            : '<span class="vpill vpill-fail">✗</span>';
    } catch { return ''; }
}

function recomputeInlineVerification(): void {
    if (!lastResults.length) return;
    lastResults.forEach((r, i) => {
        $(`[data-idx="${i}"]`).html(computeVerifyBadge(r.translation));
    });
    updatePassCount();
}

function updatePassCount(): void {
    const vtype   = String($('input[name=vtype]:checked').val());
    const vcontent = String($('#vc-content').val() ?? '').trim();
    if (!vcontent || vtype !== 'regex') { $('#pass-count').text(''); return; }
    const polarity = String($('input[name=polarity]:checked').val() || 'positive');
    let pass = 0, total = 0;
    try {
        const rx = new RegExp(vcontent, 'i');
        lastResults.forEach(r => {
            if (r.translation === null) return;
            total++;
            const matched = rx.test(r.translation);
            const passes  = polarity === 'negative' ? !matched : matched;
            if (passes) pass++;
        });
        if (total === 0) { $('#pass-count').text(''); return; }
        const cls = pass === 0 ? 'count-fail' : (pass === total ? 'count-pass' : 'count-partial');
        $('#pass-count').html(`<span class="${cls}">${pass}/${total} pass verification</span>`);
    } catch { $('#pass-count').text(''); }
}

function getSelectedTranslation(): string {
    const r = lastResults[selectedIdx];
    return r?.translation ?? '';
}

// ---- Sidebar: my submissions ----

async function loadMySuggestions(): Promise<void> {
    try {
        const sugs = await getSuggestions();
        const $el = $('#my-list');
        if (!sugs.length) { $el.html('<div class="empty">No submissions yet</div>'); return; }
        $el.html(sugs.map(renderMySug).join(''));
    } catch { /* ignore */ }
}

function renderMySug(s: Suggestion): string {
    const srcPreview = s.source_text.length > 60 ? s.source_text.slice(0, 60) + '…' : s.source_text;
    const polarity = s.verification_polarity === 'negative' ? ' (neg)' : '';
    return `<div class="sug-mini">
        <div class="sug-mini-meta">#${s.id} &middot; ${s.source_lang}&rarr;${s.target_lang} &middot; ${fmtDate(s.created_at)}</div>
        <div class="sug-mini-text">${escHtml(srcPreview)}</div>
        <div class="sug-mini-tr">${escHtml(s.translation)}</div>
        <div class="sug-mini-footer">
          <code class="sug-mini-vc">${escHtml(s.verification_content)}${escHtml(polarity)}</code>
          ${scoreBadge(s.points)}
        </div>
    </div>`;
}

function escHtml(str: string): string { return $('<div>').text(str).html(); }

function fmtDate(dt: string): string { return (dt ?? '').replace('T', ' ').slice(0, 16); }

function scoreBadge(p: number): string {
    if (p < 0) return '<span class="badge badge-pending">Pending</span>';
    const labels = ['0 · Rejected', '1 · Poor', '2 · Good', '3 · Excellent'];
    return `<span class="badge badge-score-${p}">${labels[p]}</span>`;
}
