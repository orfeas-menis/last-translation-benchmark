import $ from 'jquery';

const TOKEN_KEY = 'ltb_token';

// ---------- Types ----------

export interface User {
    username: string;
    role: 'annotator' | 'senior';
    quota_used: number;
    quota_remaining: number;
    daily_quota: number;
    total_points: number;
}

export interface Suggestion {
    id: number;
    user_id: number;
    username: string;
    source_text: string;
    translation: string;
    source_lang: string;
    target_lang: string;
    verification_type: 'regex' | 'llm';
    verification_content: string;
    verification_polarity: 'positive' | 'negative';
    points: number;
    created_at: string;
}

// ---------- Token helpers ----------

export function getToken(): string | null {
    return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
    localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
    localStorage.removeItem(TOKEN_KEY);
}

// ---------- Generic fetch ----------

function apiCall<T>(method: string, url: string, data?: object): Promise<T> {
    const token = getToken();
    return new Promise<T>((resolve, reject) => {
        const settings: JQuery.AjaxSettings = {
            url,
            method,
            contentType: 'application/json',
            dataType: 'json',
            success: (x: T) => resolve(x),
            error: (xhr: JQuery.jqXHR) => {
                const detail = (xhr.responseJSON as { detail?: string })?.detail ?? 'Request failed';
                reject(detail);
            },
        };
        if (token) settings.headers = { Authorization: `Bearer ${token}` };
        if (data !== undefined) settings.data = JSON.stringify(data);
        $.ajax(settings);
    });
}

// ---------- API calls ----------

export function login(username: string, password: string) {
    return apiCall<{ token: string; role: string; username: string }>(
        'POST', '/api/login', { username, password }
    );
}

export function logout() {
    return apiCall<{ ok: boolean }>('POST', '/api/logout');
}

export function getMe() {
    return apiCall<User>('GET', '/api/me');
}

export function translate(text: string, source_lang: string, target_lang: string) {
    return apiCall<{
        results: Array<{ api: string; translation: string | null; error: string | null }>;
        quota_remaining: number;
    }>('POST', '/api/translate', { text, source_lang, target_lang });
}

export function verify(
    translation: string,
    verification_type: string,
    verification_content: string,
    verification_polarity: string = 'positive',
) {
    return apiCall<{ verified: boolean; detail: string }>(
        'POST', '/api/verify', { translation, verification_type, verification_content, verification_polarity }
    );
}

export function getSuggestions() {
    return apiCall<Suggestion[]>('GET', '/api/suggestions');
}

export function createSuggestion(data: {
    source_text: string;
    translation: string;
    source_lang: string;
    target_lang: string;
    verification_type: string;
    verification_content: string;
    verification_polarity: string;
}) {
    return apiCall<{ ok: boolean }>('POST', '/api/suggestions', data);
}

export function scoreSuggestion(id: number, points: number) {
    return apiCall<{ ok: boolean }>('POST', `/api/suggestions/${id}/score`, { points });
}
