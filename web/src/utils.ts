import $ from 'jquery';
import { Comment } from './api';

export const esc = (s: string) => $('<div>').text(s).html();
export const fmtDate = (d: string) => (d || '').replace('T', ' ').slice(0, 16);

export function renderHeaderStatus(user: { username: string, quota_used: number, quota: number, total_accepted: number }): void {
    $('#header-status').css('display', 'flex');
    $('#quota-text').text(`Translation credits: ${(user.quota ?? 0) - (user.quota_used ?? 0)}`);
    $('#total-points').text(user.total_accepted ?? 0);
    $('#username-info').text(user.username);
}

export function showToast(msg: string): void {
    const t = $('#toast').text(msg).addClass('show');
    setTimeout(() => t.removeClass('show'), 2000);
}

export function scoreBadge(status: 'pending' | 'accept' | 'reject', hasComments?: boolean): string {
    if (status === 'pending') return '<span class="badge badge-pending">Pending</span>';
    if (status === 'accept') return '<span class="badge badge-score-3">✓ Accepted</span>';
    return '<span class="badge badge-score-0">✗ Rejected</span>';
}

function getUsernameColor(username: string): string {
    let hash = 0;
    for (let i = 0; i < username.length; i++) {
        hash = username.charCodeAt(i) + ((hash << 5) - hash);
    }
    const h = hash % 360;
    return `hsl(${h}, 70%, 90%)`;
}


export function renderCommentThread(comments: Comment[] | undefined, currentUsername: string): string {
    if (!comments?.length) return '';
    return `<div class="comment-thread">${comments.map(c => {
        const isOwn = c.author === currentUsername;
        const align = isOwn ? 'flex-end' : 'flex-start';
        const bg = getUsernameColor(c.author);
        return `<div class="comment-msg" style="align-self: ${align}; background: ${bg};">
            <span class="comment-author" title="${esc(c.timestamp)}" style="cursor: help;">${esc(c.author)}</span>
            <div class="comment-body">${esc(c.text)}</div>
        </div>`;
    }).join('')}</div>`;
}

export function accessDenied(roles: string[], target: string): void {
    document.body.innerHTML = `<div style="padding: 2rem; text-align: center;">
        <h2>Access Denied</h2>
        <p>You have roles: ${roles.map(x => `<em>${esc(x)}</em>`).join(', ')}.<br>Need: <em>${esc(target)}</em>.</p>
    </div>`;
}


