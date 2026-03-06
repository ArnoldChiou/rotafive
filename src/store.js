import { reactive, computed } from 'vue';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080/api';

// ─── Auth helpers ─────────────────────────────────────────────────────────────
// Use sessionStorage so each browser tab can be logged in as a different user
// (e.g. Client in Tab 1, Freelancer in Tab 2)
function getToken() {
    return sessionStorage.getItem('rotafive_token') || null;
}

function saveToken(token) {
    sessionStorage.setItem('rotafive_token', token);
}

function clearToken() {
    sessionStorage.removeItem('rotafive_token');
}

function authHeaders() {
    const token = getToken();
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    return headers;
}

// ─── Store ────────────────────────────────────────────────────────────────────
export const store = reactive({
    token: getToken(),
    user: null,         // { id, email, role }
    freelancers: [],
    socket: null,       // WebSocket instance

    availableSkills: computed(() => [
        'Data Science', 'Design', 'Django', 'Docker', 'Figma', 'Flask', 'Illustration', 'JavaScript',
        'Logo Design', 'Machine Learning', 'Next.js', 'Node.js', 'Nuxt', 'Photoshop', 'Python', 'React', 'SQL',
        'Tailwind', 'TypeScript', 'UI/UX', 'Vue', 'Web Design'
    ].sort()),

    // ─── Auth ──────────────────────────────────────────────────────────────────
    async login(email, password) {
        try {
            // OAuth2 form format
            const body = new URLSearchParams({ username: email, password });
            const res = await fetch(`${API_BASE}/auth/token`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: body.toString()
            });
            if (!res.ok) return false;
            const data = await res.json();
            this.token = data.access_token;
            saveToken(data.access_token);
            await this.fetchMe();
            return true;
        } catch (err) {
            console.error('Login error:', err);
            return false;
        }
    },

    async register(email, password, role, name = '', skills = []) {
        try {
            const res = await fetch(`${API_BASE}/auth/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password, role, name: name || undefined, skills })
            });
            const data = await res.json();
            if (!res.ok) return { success: false, message: data.detail || 'Registration failed' };
            return { success: true };
        } catch (err) {
            return { success: false, message: 'Network error' };
        }
    },

    async fetchMe() {
        try {
            const res = await fetch(`${API_BASE}/auth/me`, { headers: authHeaders() });
            if (res.ok) this.user = await res.json();
        } catch (err) {
            console.error('fetchMe error:', err);
        }
    },

    logout() {
        this.token = null;
        this.user = null;
        this.freelancers = [];
        this.disconnectWebSocket();
        clearToken();
    },

    // ─── WebSocket Logic ─────────────────────────────────────────────────────────
    connectWebSocket(projectId, onMessageCallback) {
        this.disconnectWebSocket(); // Ensure no duplicates
        if (!this.token) return;

        const wsUrl = `ws://${window.location.host}/ws/project/${projectId}?token=${this.token}`;
        // If API_BASE is different host in dev: Use VITE_API_BASE_URL converted to ws://
        const baseWsUrl = API_BASE.replace('http://', 'ws://').replace('https://', 'wss://').replace('/api', '');
        const fullWsUrl = `${baseWsUrl}/ws/project/${projectId}?token=${this.token}`;

        this.socket = new WebSocket(fullWsUrl);

        this.socket.onopen = () => {
            console.log(`WebSocket connected for project ${projectId}`);
        };

        this.socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (onMessageCallback) onMessageCallback(data);
            } catch (err) {
                console.error("WebSocket message parsing error", err);
            }
        };

        this.socket.onclose = () => {
            console.log(`WebSocket disconnected. Reconnecting...`);
            setTimeout(() => {
                if (this.user) {
                    this.connectWebSocket(projectId, onMessageCallback);
                }
            }, 3000); // Reconnect in 3s
        };
    },

    disconnectWebSocket() {
        if (this.socket) {
            this.socket.onclose = null; // Prevent reconnect loop
            this.socket.close();
            this.socket = null;
        }
    },

    // ─── Freelancers ──────────────────────────────────────────────────────────
    async fetchFreelancers() {
        try {
            const res = await fetch(`${API_BASE}/freelancers`, { headers: authHeaders() });
            if (res.ok) {
                const data = await res.json();
                data.forEach(f => {
                    if (typeof f.skills === 'string') {
                        try { f.skills = JSON.parse(f.skills); } catch (e) { }
                    }
                });
                this.freelancers = data;
            }
        } catch (err) {
            console.error('fetchFreelancers error:', err);
        }
    },

    // ─── Matching ─────────────────────────────────────────────────────────────
    async getMatches(requiredSkills) {
        let url = `${API_BASE}/match`;
        if (requiredSkills?.length > 0) url += `?skills=${encodeURIComponent(requiredSkills.join(','))}`;
        try {
            const res = await fetch(url, { headers: authHeaders() });
            if (!res.ok) {
                console.error('Match API error:', res.status, await res.text());
                return { project_id: null, matches: [] };
            }
            const data = await res.json();
            if (data.matches) {
                data.matches.forEach(f => {
                    if (typeof f.skills === 'string') {
                        try { f.skills = JSON.parse(f.skills); } catch (e) { }
                    }
                });
            }
            return { project_id: data.project_id, matches: data.matches || [] };
        } catch (err) {
            console.error('Match error:', err);
            return { project_id: null, matches: [] };
        }
    },

    async inviteFreelancer(freelancerId, projectId) {
        try {
            const res = await fetch(`${API_BASE}/invite`, {
                method: 'POST',
                headers: authHeaders(),
                body: JSON.stringify({ freelancer_id: freelancerId, project_id: projectId })
            });
            return res.ok;
        } catch (err) {
            console.error('Invite error:', err);
            return false;
        }
    },

    async selectFreelancer(freelancerId, projectId = null) {
        try {
            const res = await fetch(`${API_BASE}/respond-invitation`, {
                method: 'POST',
                headers: authHeaders(),
                body: JSON.stringify({ freelancer_id: freelancerId, project_id: projectId || 1, action: 'accept' })
            });
            if (res.ok) {
                setTimeout(() => {
                    fetch(`${API_BASE}/reset-cooling?freelancer_id=${freelancerId}`, {
                        method: 'POST', headers: authHeaders()
                    });
                }, 15000);
                await this.fetchFreelancers();
                return true;
            }
            return false;
        } catch (err) {
            console.error('Select error:', err);
            return false;
        }
    },

    async declineInvitation(freelancerId, projectId) {
        try {
            const res = await fetch(`${API_BASE}/respond-invitation`, {
                method: 'POST',
                headers: authHeaders(),
                body: JSON.stringify({ freelancer_id: freelancerId, project_id: projectId, action: 'decline' })
            });
            if (res.ok) {
                const data = await res.json();
                if (data.replaced_with) {
                    let newF = data.replaced_with;
                    if (typeof newF.skills === 'string') {
                        try { newF.skills = JSON.parse(newF.skills); } catch (e) { }
                    }
                    return newF;
                }
                return null;
            }
            return null;
        } catch (err) {
            console.error('Decline error:', err);
            return null;
        }
    },

    async fetchInvitations() {
        try {
            const res = await fetch(`${API_BASE}/invitations`, { headers: authHeaders() });
            if (res.ok) return await res.json();
            return [];
        } catch (err) {
            console.error('fetchInvitations error:', err);
            return [];
        }
    }
});

// Rehydrate user on page load if token exists
if (store.token) {
    store.fetchMe();
}
