import './style.css';
import $ from 'jquery';
import { login, getToken, getMe, setToken } from './api';

$(async () => {
    // Redirect if already logged in
    const token = getToken();
    if (token) {
        try {
            const user = await getMe();
            redirectByRole(user.role);
            return;
        } catch {
            // Token invalid — fall through to show login form
        }
    }

    $('#login-form').on('submit', async (e) => {
        e.preventDefault();
        const username = String($('#l-user').val() ?? '').trim();
        const password = String($('#l-pass').val() ?? '');
        if (!username || !password) return;

        try {
            const data = await login(username, password);
            setToken(data.token);
            redirectByRole(data.role);
        } catch (err) {
            $('#l-err').text(String(err)).show();
        }
    });
});

function redirectByRole(role: string): void {
    window.location.href = role === 'senior' ? '/senior.html' : '/annotator.html';
}
