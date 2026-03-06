import { reactive, computed } from 'vue';

const API_BASE_URL = 'http://localhost:8080/api';

export const store = reactive({
    freelancers: [], // Will hold real data fetched

    // All unique skills available (Keep static or fetch if you prefer, but we can compute from fetched freelancers)
    availableSkills: computed(() => {
        // If we want a static robust list based on existing mocks:
        return [
            'Data Science', 'Design', 'Django', 'Docker', 'Figma', 'Flask', 'Illustration', 'JavaScript',
            'Logo Design', 'Machine Learning', 'Next.js', 'Node.js', 'Nuxt', 'Photoshop', 'Python', 'React', 'SQL',
            'Tailwind', 'TypeScript', 'UI/UX', 'Vue', 'Web Design'
        ].sort();
    }),

    async fetchFreelancers() {
        try {
            const response = await fetch(`${API_BASE_URL}/freelancers`);
            if (response.ok) {
                // data: [{id: 1, name: 'Alice', skills: '["Vue"]', rating: 4.8, status: 'idle', last_assigned_at: 'string'}]
                const data = await response.json();

                // Parse JSON strings in skills (asyncpg stringifies jsonb sometimes, or fastApi does as list directly depending on query)
                data.forEach(f => {
                    if (typeof f.skills === 'string') {
                        try {
                            f.skills = JSON.parse(f.skills);
                        } catch (e) { /* ignore */ }
                    }
                });
                this.freelancers = data;
            }
        } catch (err) {
            console.error('Failed to fetch freelancers:', err);
        }
    },

    // The rotational match algorithm via Backend GET /api/match
    async getMatches(requiredSkills) {
        let url = `${API_BASE_URL}/match`;
        if (requiredSkills && requiredSkills.length > 0) {
            url += `?skills=${encodeURIComponent(requiredSkills.join(','))}`;
        }

        try {
            const response = await fetch(url);
            const data = await response.json();

            // data is now { project_id: int, matches: [...] }
            if (data.matches) {
                data.matches.forEach(f => {
                    if (typeof f.skills === 'string') {
                        try {
                            f.skills = JSON.parse(f.skills);
                        } catch (e) { }
                    }
                });
            }
            return data;
        } catch (err) {
            console.error("Match error:", err);
            return { project_id: null, matches: [] };
        }
    },

    // Invite a specific freelancer explicitly
    async inviteFreelancer(freelancerId, projectId) {
        try {
            const payload = {
                freelancer_id: freelancerId,
                project_id: projectId
            };
            const response = await fetch(`${API_BASE_URL}/invite`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            return response.ok;
        } catch (err) {
            console.error("Invite error:", err);
            return false;
        }
    },

    // Cycle completion via Backend POST /api/select (Legacy, but updated to use respond logic)
    async selectFreelancer(freelancerId, projectId = null) {
        try {
            const payload = {
                freelancer_id: freelancerId,
                project_id: projectId || 1,
                action: 'accept'
            }
            const response = await fetch(`${API_BASE_URL}/respond-invitation`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                setTimeout(() => {
                    fetch(`${API_BASE_URL}/reset-cooling?freelancer_id=${freelancerId}`, { method: 'POST' });
                }, 15000);

                await this.fetchFreelancers();

                // Broadcast to other tabs
                const bc = new BroadcastChannel('rotafive_sync');
                bc.postMessage({ type: 'ACCEPTED', projectId, freelancerId });
                bc.close();

                return true;
            }
            return false;
        } catch (err) {
            console.error("Select error:", err);
            return false;
        }
    },

    // Decline invitation and get auto-replacement
    async declineInvitation(freelancerId, projectId) {
        try {
            const payload = {
                freelancer_id: freelancerId,
                project_id: projectId,
                action: 'decline'
            };
            const response = await fetch(`${API_BASE_URL}/respond-invitation`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                const data = await response.json();

                if (data.replaced_with) {
                    let newFreelancer = data.replaced_with;
                    if (typeof newFreelancer.skills === 'string') {
                        try {
                            newFreelancer.skills = JSON.parse(newFreelancer.skills);
                        } catch (e) { }
                    }

                    // Broadcast to other tabs
                    const bc = new BroadcastChannel('rotafive_sync');
                    bc.postMessage({
                        type: 'DECLINED_REPLACED',
                        projectId,
                        declinedId: freelancerId,
                        replacement: newFreelancer
                    });
                    bc.close();

                    return newFreelancer;
                }

                // Even if no replacement, broadcast decline
                const bc = new BroadcastChannel('rotafive_sync');
                bc.postMessage({ type: 'DECLINED_NO_REPLACEMENT', projectId, declinedId: freelancerId });
                bc.close();

                return null;
            }
            return null;
        } catch (err) {
            console.error("Decline error:", err);
            return null;
        }
    },

    // Used by Freelancer Mock View
    async fetchInvitations() {
        try {
            const response = await fetch(`${API_BASE_URL}/invitations`);
            if (response.ok) {
                return await response.json();
            }
            return [];
        } catch (err) {
            console.error("fetchInvitations error", err);
            return [];
        }
    }
});
