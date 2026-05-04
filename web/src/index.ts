import './style.css';
import $ from 'jquery';

import { getToken, getUsername, getMe, User } from './api';
import { setupInstructions } from './utils';

$(async () => {
    setupInstructions('all');

    const token = getToken();
    const username = getUsername();
    if (token && username) {
        try {
            const user = await getMe();
            showRoleButtons(user);
        } catch {
            $('#auth-error').show();
        }
    }
});

function showRoleButtons(user: User): void {
    $('#register-btn').hide();
    $('#cta-info-unauth').hide();

    const search = window.location.search;
    const container = $('#role-buttons');

    container.append(`<span>Hello ${user.name}!</span><br><br>`);

    if (user.roles.includes('contributor')) {
        container.append(`<a href="contribute${search}" class="btn btn-secondary">✍️ Contribute</a>`);
    }
    if (user.roles.includes('reviewer')) {
        container.append(`<a href="review${search}" class="btn btn-secondary">🔍 Review</a>`);
    }
    if (user.roles.includes('admin')) {
        container.append(`<a href="admin${search}" class="btn btn-secondary">⚙️ Admin</a>`);
    }

    container.css('display', 'block');
}
