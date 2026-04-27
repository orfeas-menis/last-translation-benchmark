import $ from 'jquery';
import { Comment } from './api';

export const esc = (s: string) => $('<div>').text(s).html();
export const fmtDate = (d: string) => (d || '').replace('T', ' ').slice(0, 16);

export function showToast(msg: string): void {
    const t = $('#toast').text(msg).addClass('show');
    setTimeout(() => t.removeClass('show'), 2000);
}

export function scoreBadge(p: number, comment?: string): string {
    if (p < 0) return comment ? '<span class="badge badge-score-1">💬 Commented</span>' : '<span class="badge badge-pending">Pending</span>';
    return `<span class="badge badge-score-${p === 1 ? 3 : 0}">${['✗ Rejected', '✓ Accepted'][p] ?? p}</span>`;
}

export function renderCommentThread(comments: Comment[] | undefined, viewerRole: 'reviewer' | 'contributor'): string {
    if (!comments?.length) return '';
    return `<div class="comment-thread">${comments.map(c => {
        const cls = c.role === viewerRole ? 'comment-msg-contributor' : 'comment-msg-reviewer';
        return `<div class="comment-msg ${cls}">
            <span class="comment-author">${esc(c.author)}</span>
            <span class="comment-ts">${esc(c.timestamp)}</span>
            <div class="comment-body">${esc(c.text)}</div>
        </div>`;
    }).join('')}</div>`;
}

export function accessDenied(roles: string[], target: string): void {
    document.body.innerHTML = `<div style="padding: 2rem; text-align: center;">
        <h2>Access Denied</h2>
        <p>You have roles: ${roles.join(', ')}. Need: "${target}".</p>
    </div>`;
}
