<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import { store } from '../store.js';
import { Mail, CheckCircle, XCircle } from 'lucide-vue-next';

const invitations = ref([]);
const activeSockets = {};

const loadInvitations = async () => {
    invitations.value = await store.fetchInvitations();

    // Disconnect old connections for projects that are no longer active
    for (let pid in activeSockets) {
        if (!invitations.value.find(inv => String(inv.project_id) === String(pid))) {
            activeSockets[pid].close();
            delete activeSockets[pid];
        }
    }

    // Connect new connections for pending invitations to listen to sibling responses
    for (let inv of invitations.value) {
        if (!activeSockets[inv.project_id]) {
            const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080/api';
            const baseWsUrl = apiBase.replace('http://', 'ws://').replace('https://', 'wss://').replace('/api', '');
            const ws = new WebSocket(`${baseWsUrl}/ws/project/${inv.project_id}?token=${store.token}`);
            
            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === 'ACCEPTED' || data.type === 'DECLINED_REPLACED') {
                        // Another freelancer responded, or we were replaced! Refresh the list.
                        loadInvitations();
                    }
                } catch (e) {}
            };
            activeSockets[inv.project_id] = ws;
        }
    }
};

let globalWs = null;

onMounted(() => {
    loadInvitations();

    // Attach to global freelancer socket to listen for NEW invites
    if (store.user && store.user.role === 'freelancer') {
        const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080/api';
        const baseWsUrl = apiBase.replace('http://', 'ws://').replace('https://', 'wss://').replace('/api', '');
        globalWs = new WebSocket(`${baseWsUrl}/ws/freelancer/${store.user.id}?token=${store.token}`);
        globalWs.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'INVITED') {
                    // New job!
                    loadInvitations();
                }
            } catch(e) {}
        }
    }
});

onUnmounted(() => {
    for (let pid in activeSockets) {
         activeSockets[pid].close();
    }
    if (globalWs) {
        globalWs.close();
    }
});

const handleRespond = async (freelancerId, projectId, action) => {
    // If accept, we use the selectFreelancer endpoint which we modified to act as 'accept'
    // Actually our selectFreelancer triggers `/respond-invitation` with action 'accept'
    if (action === 'accept') {
        const success = await store.selectFreelancer(freelancerId, projectId);
        if (success) {
            loadInvitations();
        } else {
            alert("Failed to accept invitation.");
        }
    } else if (action === 'decline') {
        const replacement = await store.declineInvitation(freelancerId, projectId);
        loadInvitations();
        if (!replacement) {
            console.warn("Declined, but no replacement was found.");
        }
    }
};

const formatTime = (timeStr) => {
  if (!timeStr) return '';
  const date = new Date(timeStr);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
};
</script>

<template>
  <div class="px-4 py-8 md:py-12 w-full max-w-4xl mx-auto">
    <div class="text-center mb-8">
      <h1 class="text-3xl font-bold flex items-center justify-center gap-2">
        <Mail class="w-8 h-8 text-primary" />
        Freelancer Inbox Simulation
      </h1>
      <p class="text-base-content/70 mt-2">
        Test the Auto-Replacement flow by responding to job invitations as a freelancer. 
      </p>
    </div>

    <!-- Active Invitations List -->
    <div v-if="invitations.length === 0" class="text-center p-12 bg-base-200 rounded-box border border-base-300 border-dashed">
      <div class="text-4xl mb-3">📭</div>
      <h4 class="text-xl font-bold">No Pending Invitations</h4>
      <p class="text-base-content/70">When clients search and find matches, they will appear here.</p>
    </div>

    <div v-else class="space-y-4">
      <TransitionGroup name="list">
        <div v-for="inv in invitations" :key="inv.freelancer_id + '-' + inv.project_id" 
             class="card bg-base-100 shadow-lg border border-base-200">
          <div class="card-body p-6 flex flex-col md:flex-row items-center gap-4">
            
            <div class="flex-1">
              <div class="flex items-center gap-2 mb-1">
                <span class="badge badge-primary">New Job</span>
                <span class="text-xs text-base-content/50">{{ formatTime(inv.created_at) }}</span>
              </div>
              <h2 class="card-title text-xl mb-1">Project: {{ inv.project_title }}</h2>
              <p class="text-base-content/80">
                Hello <strong>{{ inv.freelancer_name }}</strong>, you have been matched for this job!
              </p>
            </div>

            <div class="flex gap-2 w-full md:w-auto mt-4 md:mt-0">
              <button @click="handleRespond(inv.freelancer_id, inv.project_id, 'accept')" 
                      class="btn btn-success text-white grow md:grow-0">
                <CheckCircle class="w-4 h-4" /> Accept
              </button>
              <button @click="handleRespond(inv.freelancer_id, inv.project_id, 'decline')" 
                      class="btn btn-error btn-outline grow md:grow-0">
                <XCircle class="w-4 h-4" /> Decline
              </button>
            </div>
          </div>
        </div>
      </TransitionGroup>
    </div>
  </div>
</template>

<style scoped>
.list-enter-active,
.list-leave-active {
  transition: all 0.4s ease;
}
.list-enter-from {
  opacity: 0;
  transform: translateX(-30px);
}
.list-leave-to {
  opacity: 0;
  transform: translateX(30px);
}
</style>
