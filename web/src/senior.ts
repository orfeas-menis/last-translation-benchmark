import './style.css';
import $ from 'jquery';
import {
    getToken, clearToken, getMe, logout,
    getSuggestions, scoreSuggestion,
    Suggestion,
} from './api';

let allSugs: Suggestion[] = [];
let curFilter = 'pending';

$(async () => {
    if (!getToken()) { window.location.href = '/'; return; }

    try {
        const user = await getMe();
        if (user.role !== 'senior') { window.location.href = '/annotator.html'; return; }
        $('#sen-info').text(`${user.username} · Senior Reviewer`);
    } catch {
        clearToken();
        window.location.href = '/';
        return;
    }

    await loadSuggestions();

    // Filter tabs
    $('.tab[data-filter]').on('click', function () {
        curFilter = String($(this).data('filter'));
        $('.tab').removeClass('active');
        $(this).addClass('active');
        renderList();
    });

    // Refresh
    $('#refresh-btn').on('click', loadSuggestions);

    // Score buttons (event delegation — list re-renders on each load)
    $('#sen-list').on('click', '.score-btn', async function () {
        const id     = parseInt(String($(this).data('id')));
        const points = parseInt(String($(this).data('points')));
        try {
            await scoreSuggestion(id, points);
            const sug = allSugs.find(s => s.id === id);
            if (sug) sug.points = points;
            const $item = $(`#sug-${id}`);
            $item.find('.score-btn').removeClass('active');
            $(this).addClass('active');
            $item.find('.sug-meta .badge').replaceWith(scoreBadge(points));
            if (curFilter === 'pending') {
                setTimeout(() => {
                    $item.fadeOut(250, function () {
                        $(this).remove();
                        if (!$('#sen-list .sug-item').length) {
                            $('#sen-list').html('<div class="empty">No pending suggestions</div>');
                        }
                    });
                }, 400);
            }
        } catch { alert('Failed to save score'); }
    });

    // Logout
    $('#logout-btn').on('click', async () => {
        try { await logout(); } finally { clearToken(); window.location.href = '/'; }
    });
});

async function loadSuggestions(): Promise<void> {
    $('#sen-list').html('<div class="empty">Loading…</div>');
    try {
        allSugs = await getSuggestions();
        renderList();
    } catch {
        $('#sen-list').html('<div class="empty">Failed to load suggestions</div>');
    }
}

function renderList(): void {
    let list = allSugs;
    if (curFilter === 'pending') list = allSugs.filter(s => s.points < 0);
    else if (curFilter === 'scored') list = allSugs.filter(s => s.points >= 0);

    const $el = $('#sen-list');
    if (!list.length) { $el.html('<div class="empty">No suggestions here</div>'); return; }
    $el.html(list.map(renderSug).join(''));
}

function renderSug(s: Suggestion): string {
    const btnColors = ['#ef4444', '#f59e0b', '#3b82f6', '#22c55e'];
    const btns = ([0, 1, 2, 3] as const).map(p => {
        const act = s.points === p ? ' active' : '';
        return `<button class="score-btn${act}" style="background:${btnColors[p]};color:#fff" data-id="${s.id}" data-points="${p}">${p}</button>`;
    }).join('');

    return `<div class="sug-item" id="sug-${s.id}">
        <div class="sug-meta">#${s.id} &middot; <b>${escHtml(s.username)}</b> &middot; ${s.source_lang}&rarr;${s.target_lang} &middot; ${fmtDate(s.created_at)} &middot; ${scoreBadge(s.points)}</div>
        <div class="sug-texts">
          <div class="sug-box"><div class="lbl">SOURCE</div>${escHtml(s.source_text)}</div>
          <div class="sug-box"><div class="lbl">TRANSLATION</div>${escHtml(s.translation)}</div>
        </div>
        <div class="sug-verify"><b>${s.verification_type === 'regex' ? 'Regex' : 'LLM prompt'}:</b> <code>${escHtml(s.verification_content)}</code>${s.verification_type === 'regex' && s.verification_polarity === 'negative' ? ' <span style="color:#dc2626;font-size:0.85em">(must NOT match)</span>' : ''}</div>
        <div class="sug-scoring"><span class="score-label">Score:</span>${btns}</div>
    </div>`;
}

function escHtml(str: string): string { return $('<div>').text(str).html(); }

function fmtDate(dt: string): string { return (dt ?? '').replace('T', ' ').slice(0, 16); }

function scoreBadge(p: number): string {
    if (p < 0) return '<span class="badge badge-pending">Pending</span>';
    const labels = ['0 · Rejected', '1 · Poor', '2 · Good', '3 · Excellent'];
    return `<span class="badge badge-score-${p}">${labels[p]}</span>`;
}
