import './style.css';
import $ from 'jquery';
import {
    getToken, clearToken, getMe, logout,
    translate, verify, createSuggestion, getSuggestions,
    User, Suggestion,
} from './api';

let currentUser: User | null = null;

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
    renderQuota(currentUser.quota_remaining, currentUser.daily_quota);
    loadMySuggestions();

    // Verification type toggle
    $('input[name=vtype]').on('change', function () {
        if ($(this).val() === 'llm') {
            $('#vc-label').html('LLM prompt <span class="hint">(used to verify the translation)</span>');
            $('#vc-content').attr('placeholder', 'e.g. Does the translation preserve the pun from the source text?');
        } else {
            $('#vc-label').html('Regex pattern <span class="hint">(matched against translation)</span>');
            $('#vc-content').attr('placeholder', 'e.g. \\bword\\b');
        }
    });

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
            $('#tgt-text').val(data.translation);
            $('#tr-status').text('✓ Done');
            currentUser!.quota_remaining = data.quota_remaining;
            renderQuota(data.quota_remaining, currentUser!.daily_quota);
        } catch (err) {
            $('#tr-status').text(`✗ ${err}`);
        } finally {
            $('#tr-btn').prop('disabled', false);
        }
    });

    // Test verification
    $('#verify-btn').on('click', async () => {
        const translation = String($('#tgt-text').val() ?? '').trim();
        const vtype       = String($('input[name=vtype]:checked').val());
        const vcontent    = String($('#vc-content').val() ?? '').trim();
        if (!translation) { $('#verify-result').html('<span class="msg-err">No translation to verify</span>'); return; }
        if (!vcontent)    { $('#verify-result').html('<span class="msg-err">No verification content</span>'); return; }
        try {
            const data = await verify(translation, vtype, vcontent);
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
        const translation          = String($('#tgt-text').val() ?? '').trim();
        const source_lang          = String($('#src-lang').val());
        const target_lang          = String($('#tgt-lang').val());
        const verification_type    = String($('input[name=vtype]:checked').val());
        const verification_content = String($('#vc-content').val() ?? '').trim();

        if (!source_text || !translation || !verification_content) {
            $('#submit-status').html('<span class="msg-err">Please fill all required fields</span>');
            return;
        }
        try {
            await createSuggestion({ source_text, translation, source_lang, target_lang, verification_type, verification_content });
            $('#submit-status').html('<span class="msg-ok">✓ Submitted!</span>');
            $('#src-text, #tgt-text, #vc-content').val('');
            $('#verify-result').html('');
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

function renderQuota(remaining: number, total: number): void {
    const pct = total > 0 ? (remaining / total * 100) : 0;
    $('#quota-fill').css('width', `${pct}%`);
    $('#quota-text').text(`${remaining} / ${total} remaining`);
}

async function loadMySuggestions(): Promise<void> {
    try {
        const sugs = await getSuggestions();
        const $el = $('#my-list');
        if (!sugs.length) { $el.html('<div class="empty">No submissions yet</div>'); return; }
        $el.html(sugs.map(renderMySug).join(''));
    } catch { /* ignore */ }
}

function renderMySug(s: Suggestion): string {
    return `<div class="sug-item">
        <div class="sug-meta">#${s.id} &middot; ${s.source_lang}&rarr;${s.target_lang} &middot; ${fmtDate(s.created_at)} &middot; ${scoreBadge(s.points)}</div>
        <div class="sug-texts">
          <div class="sug-box"><div class="lbl">SOURCE</div>${escHtml(s.source_text)}</div>
          <div class="sug-box"><div class="lbl">TRANSLATION</div>${escHtml(s.translation)}</div>
        </div>
        <div class="sug-verify"><b>${s.verification_type === 'regex' ? 'Regex' : 'LLM'}:</b> <code>${escHtml(s.verification_content)}</code></div>
    </div>`;
}

function escHtml(str: string): string { return $('<div>').text(str).html(); }

function fmtDate(dt: string): string { return (dt ?? '').replace('T', ' ').slice(0, 16); }

function scoreBadge(p: number): string {
    if (p < 0) return '<span class="badge badge-pending">Pending</span>';
    const labels = ['0 · Rejected', '1 · Poor', '2 · Good', '3 · Excellent'];
    return `<span class="badge badge-score-${p}">${labels[p]}</span>`;
}
