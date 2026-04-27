import './style.css';
import $ from 'jquery';
import { getToken, getMe, updateProfile } from './api';

$(async () => {
    if (!getToken()) { window.location.href = 'index.html'; return; }

    try {
        const user = await getMe();
        // Pre-fill existing profile data
        if (user.name) $('#name').val(user.name);
        if (user.affiliation) $('#affiliation').val(user.affiliation);
        if (user.email) $('#email').val(user.email);
        if (user.credit_consent) $('#credit-consent').prop('checked', true);
    } catch {
        window.location.href = 'index.html';
        return;
    }

    $('#save-btn').on('click', async () => {
        const name = String($('#name').val()).trim();
        const affiliation = String($('#affiliation').val()).trim();
        const email = String($('#email').val()).trim();
        const credit_consent = Boolean($('#credit-consent').prop('checked'));

        if (!name || !email) {
            $('#status-msg').removeClass('msg-ok').addClass('msg-err').text('Name and email are required.');
            return;
        }

        $('#save-btn').prop('disabled', true);
        try {
            await updateProfile({ name, affiliation, email, credit_consent });

            // Redirect back to main page which will route appropriately
            window.location.href = 'index.html' + window.location.search;
        } catch (err) {
            $('#status-msg').removeClass('msg-ok').addClass('msg-err').text(String(err));
            $('#save-btn').prop('disabled', false);
        }
    });
});
