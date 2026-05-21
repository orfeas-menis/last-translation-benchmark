import './assets/style.css';
import $ from 'jquery';
import {
    getMe, getCookie, getAdminUsers, deleteAdminUser,
    adjustAdminQuota, updateAdminRoles, updateAdminReviewScope, renderRoleSwitcher, AdminUser,
} from './api';

import { esc, showToast, accessDenied } from './utils';

let allUsers: AdminUser[] = [];
let adminName: string = '';

function renderTable(users: AdminUser[]): void {
    if (!users.length) {
        $('#user-table').html('<div class="empty">No users found</div>');
        return;
    }
    // Slightly complicated way to get the hosting root. We could use host but that doesn't work if this is hosted from a directory.
    let root = window.location.origin + window.location.pathname.split("/").slice(0, -1).join("/");
    const rows = users.map(u => {
        const link = root + '/?user=' + encodeURIComponent(u.username) + '&token=' + encodeURIComponent(u.magic_token);
        const allRoles = ['admin', 'reviewer', 'contributor'];
        const rolesHtml = allRoles.map(r => {
            const active = u.roles.includes(r);
            return `<span class="role-tag role-${r} ${active ? '' : 'role-inactive'}" data-role="${r}">${esc(r)}</span>`;
        }).join('');

        let statusLabel: string;
        let statusTitle: string;
        if (u.total_submitted > 0) {
            statusLabel = 'submitted';
            statusTitle = u.last_active ? `Last active: ${u.last_active}` : '';
        } else if (u.last_active) {
            statusLabel = 'logged-in';
            statusTitle = `Last active: ${u.last_active}`;
        } else {
            statusLabel = 'registered';
            statusTitle = '';
        }
        const statusBadge = `<span style="font-size:0.8em;white-space:nowrap" title="${esc(statusTitle)}">${statusLabel}</span>`;

        return `<tr data-uid="${u.id}">
            <td><a href="${link}" class="uname" target="_blank">${esc(u.username)}</a></td>
            <td style="width:1%;white-space:nowrap">${rolesHtml}</td>
            <td class="scope-cell" data-uid="${u.id}" title="Click to edit language scope">${u.review_langs && u.review_langs.length ? esc(u.review_langs.join(',')) : '<span class="muted">all</span>'}</td>
            <td>${u.name ? esc(u.name) : '<span class="muted">—</span>'}</td>
            <td>${u.affiliation ? esc(u.affiliation) : '<span class="muted">—</span>'}</td>
            <td class="email-cell"><a href="mailto:${esc(u.email)}">${esc(u.email)}</a></td>
            <td style="text-align:right;white-space:nowrap">${u.quota_used}&nbsp;/&nbsp;<button class="act-btn act-quota" data-uid="${u.id}" title="Adjust quota">${u.quota}</button></td>
            <td style="text-align:right">${u.total_accepted}&nbsp;/&nbsp;${u.total_submitted}</td>
            <td>${statusBadge}</td>
            <td>
              <div class="action-btns">
                <button class="act-btn act-delete" data-uid="${u.id}" title="Remove user">✕</button>
              </div>
            </td>
        </tr>`;
    }).join('');

    $('#user-table').html(`<table>
        <thead><tr><th>Username</th><th style="width:1%;white-space:nowrap">Roles</th><th class="scope-cell">Scope</th><th>Name</th><th>Affiliation</th><th>Email</th><th style="text-align:right">Used&nbsp;/<br>Quota</th><th style="text-align:right">Accepted&nbsp;/<br>Submitted</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody>${rows}</tbody>
    </table>`);

    $('.role-tag').on('click', async function () {
        const uid = $(this).closest('tr').data('uid');
        const role = $(this).data('role');
        const u = allUsers.find(u => u.id === uid);
        if (!u) return;

        let newRoles = [...u.roles];
        if (newRoles.includes(role)) {
            newRoles = newRoles.filter(r => r !== role);
        } else {
            newRoles.push(role);
        }

        try {
            const res = await updateAdminRoles(uid, newRoles);
            u.roles = res.roles;
            applyFilter();
            showToast('Roles updated');
        } catch (e) { alert(e); }
    });

    $('.act-delete').on('click', async function () {
        const uid = $(this).data('uid');
        if (!confirm(`Delete user ${uid}?`)) return;
        try {
            await deleteAdminUser(uid);
            allUsers = allUsers.filter(u => u.id !== uid);
            applyFilter();
            showToast('User deleted');
        } catch (e) { alert(e); }
    });

    $('.act-quota').on('click', async function () {
        const uid = $(this).data('uid');
        const u = allUsers.find(u => u.id === uid);
        const raw = prompt(`Adjust quota (current: ${u?.quota}, used: ${u?.quota_used}).\nUse + or - to adjust (e.g. +50 or -10):`);
        if (raw === null) return;
        if (!/^[+-]\d+$/.test(raw.trim())) { alert('Invalid input. Must start with + or - followed by a number.'); return; }
        const delta = parseInt(raw.trim(), 10);
        try {
            const res = await adjustAdminQuota(uid, delta);
            if (u) { u.quota = res.quota; u.quota_used = res.quota_used; }
            applyFilter();
            showToast('Quota updated');
        } catch (e) { alert(e); }
    });

    $('.scope-cell').on('click', async function () {
        const uid = $(this).data('uid');
        const u = allUsers.find(u => u.id === uid);
        if (!u) return;
        const current = (u.review_langs && u.review_langs.length) ? u.review_langs.join(',') : '';
        const input = prompt('Language scope (comma-separated, empty = all, e.g. English,Czech,German).\nIf you wish to prevent someone from reviewing, then remove the review role.', current);
        if (input === null) return;
        if (input.includes(', ')) { alert('Use commas without spaces (e.g. English,Czech,German).'); return; }
        const langs = input.trim() ? input.split(',').filter(Boolean) : [];
        try {
            const res = await updateAdminReviewScope(uid, langs);
            u.review_langs = res.review_langs;
            applyFilter();
            showToast('Language scope updated');
        } catch (e) { alert(e); }
    });
}

function applyFilter(): void {
    const q = ($('#filter-input').val() as string).toLowerCase().trim();
    const role = $('#role-filter').val() as string;
    const filtered = allUsers.filter(u => {
        const matchesRole = !role || u.roles.includes(role);
        const matchesQuery = !q || u.username.toLowerCase().includes(q) || (u.name || '').toLowerCase().includes(q) || (u.email || '').toLowerCase().includes(q);
        return matchesRole && matchesQuery;
    });
    $('#filtered-count').text(`Total: ${filtered.length} users`);
    renderTable(filtered);
}
$(async () => {
    if (!getCookie('ltb_token')) { window.location.href = 'index.html'; return; }
    try {
        const user = await getMe();
        adminName = user.name || user.username;
        renderRoleSwitcher(user.roles);
        if (!user.roles.includes('admin')) { accessDenied(user.roles, 'admin'); return; }
        $('#admin-info').text(user.username);
        allUsers = await getAdminUsers();
        applyFilter();
    } catch { window.location.href = 'index.html'; }

    $('#filter-input').on('input', applyFilter);
    $('#role-filter').on('change', applyFilter);
});
