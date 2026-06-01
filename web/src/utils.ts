import $ from 'jquery';
import { Comment, Submission, User, handleNotifications } from './api';

export const esc = (s: string) => $('<div>').text(s).html();
export const fmtDate = (d: string) => (d || '').replace('T', ' ').slice(0, 16);

export function renderHeaderStatus(user: User): void {
    $('#header-status').css('display', 'flex');
    $('#quota-text').text(`${(user.quota ?? 0) - (user.quota_used ?? 0)} credits left`);
    $('#total-points').text(user.total_accepted ?? 0);
    $('#username-info').text(user.username);

    if (user.notifications && $('#notif-container').length === 0) {
        const unreadCount = user.notifications.filter(n => n.status === 'unread').length;
        const notifBtn = $('<button>').css({
            background: 'black', border: 'none', cursor: 'pointer', position: 'relative', marginLeft: '10px',
            color: 'white', width: '28px', height: '28px', fontWeight: 'bold',
            display: 'flex', alignItems: 'center', justifyContent: 'center', textDecoration: 'none',
        }).text(unreadCount);

        const listDiv = $('<div>').css({
            position: 'absolute', right: '-140px', top: '27px', background: 'white',
            boxShadow: '0 4px 6px rgba(0,0,0,0.1)', padding: '10px', width: '300px', display: 'none',
            zIndex: 1000, maxHeight: '400px', overflowY: 'auto', textAlign: 'left',
        });

        const clearBtn = $('<button>').text('Clear notifications').addClass('btn-underlined').css({border: 'none', background: 'none', cursor: 'pointer', marginTop: '10px', width: '100%', textAlign: 'center', fontSize: '0.8em'})
            .on('click', async () => {
                await handleNotifications('clear');
                user.notifications = [];
                listDiv.empty();
                notifBtn.text('0');
                listDiv.hide();
            });

        if (user.notifications.length === 0) {
            listDiv.append($('<div>').text('No notifications').css({color: '#999', padding: '10px', textAlign: 'center'}));
        } else {
            user.notifications.reverse().forEach(n => {
                const item = $('<div>').css({
                    padding: '8px', borderBottom: '1px solid #eee', fontSize: '0.9em',
                    background: n.status === 'unread' ? '#f0fdf4' : 'transparent', borderRadius: '4px'
                });
                item.html(`<strong>${esc(n.type)}</strong> <small style="color:#aaa; font-size: 0.8em; margin-left: 6px;">${esc(fmtDate(n.created))}</small><br><span style="color:#666">${esc(n.content)}</span>`);
                listDiv.append(item);
            });
            listDiv.append(clearBtn);
        }

        const container = $('<div>').attr('id', 'notif-container').css('position', 'relative').append(notifBtn).append(listDiv);
        $('#header-status').append(container);

        notifBtn.on('click', async () => {
            listDiv.toggle();
            if (listDiv.is(':visible') && unreadCount > 0) {
                await handleNotifications('view');
                notifBtn.text('0');
                user.notifications.forEach(n => n.status = 'viewed');
                listDiv.children().css('background', 'transparent');
            }
        });
    }
}

export function showToast(msg: string): void {
    const t = $('#toast').text(msg).addClass('show');
    setTimeout(() => t.removeClass('show'), 2000);
}

export function scoreBadge(status: 'pending' | 'accept' | 'return', hasComments?: boolean): string {
    if (status === 'pending') return '<span class="badge badge-pending">Pending</span>';
    if (status === 'accept') return '<span class="badge badge-score-3">✓ Accepted</span>';
    return '<span class="badge badge-score-0">✗ Returned</span>';
}

function getUsernameColor(username: string): string {
    let hash = 0;
    for (let i = 0; i < username.length; i++) {
        hash = username.charCodeAt(i) + ((hash << 5) - hash);
    }
    const h = hash % 360;
    return `hsl(${h}, 30%, 90%)`;
}


export function renderCommentThread(comments: Comment[] | undefined, currentUsername: string): string {
    if (!comments?.length) return '';
    return `<div class="comment-thread">${comments.map(c => {
        const isOwn = c.author === currentUsername;
        const align = isOwn ? 'flex-end' : 'flex-start';
        const bg = getUsernameColor(c.author);
        return `<div class="comment-msg" style="align-self: ${align}; background: ${bg};">
            <span class="comment-author" title="${esc(c.created_at)}" style="cursor: help;">${esc(c.author)}</span>
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

export function renderSource(s: Submission): string {
    const isAudio = s.source_media && /^data:audio/.test(s.source_media);
    let out = '';
    if (s.source_media) {
        out += isAudio
            ? `<audio controls src="${s.source_media}" class="context_audio"></audio>`
            : `<img src="${s.source_media}" class="context_image" style="max-width:100%; max-height:150px;">`;
    }
    if (s.source_text) {
        out += `<div>${esc(s.source_text)}</div>`;
    }
    if (s.source_instructions) {
        out += `<div style="margin-top: 4px; font-size: 0.9em; color: #475569; border-left: 2px solid #cbd5e1; padding-left: 6px;"><i>Instructions:</i> ${esc(s.source_instructions)}</div>`;
    }
    return out;
}

