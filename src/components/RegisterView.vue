<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { store } from '../store.js';
import { UserPlus, Mail, Lock, User, Briefcase, AlertCircle } from 'lucide-vue-next';

const router = useRouter();
const email = ref('');
const password = ref('');
const role = ref('client');
const name = ref('');
const selectedSkills = ref([]);
const error = ref('');
const loading = ref(false);

const allSkills = [
  'Vue', 'React', 'Next.js', 'JavaScript', 'TypeScript', 'Node.js', 'Nuxt',
  'Python', 'Django', 'Flask', 'Docker', 'SQL', 'Data Science',
  'Design', 'Figma', 'UI/UX', 'Illustration', 'Web Design',
  'Tailwind', 'CSS'
].sort();

const toggleSkill = (skill) => {
  const idx = selectedSkills.value.indexOf(skill);
  if (idx >= 0) selectedSkills.value.splice(idx, 1);
  else selectedSkills.value.push(skill);
};

const handleRegister = async () => {
  error.value = '';
  if (role.value === 'freelancer' && !name.value.trim()) {
    error.value = 'Please enter your display name.';
    return;
  }
  loading.value = true;
  const result = await store.register(
    email.value, password.value, role.value,
    name.value,
    role.value === 'freelancer' ? selectedSkills.value : []
  );
  loading.value = false;
  if (result.success) {
    await store.login(email.value, password.value);
    router.push('/');
  } else {
    error.value = result.message || 'Registration failed. Please try again.';
  }
};
</script>

<template>
  <div class="min-h-screen bg-base-200 flex items-center justify-center p-4">
    <div class="card w-full max-w-md bg-base-100 shadow-2xl border border-base-200">
      <div class="card-body p-8">
        <!-- Header -->
        <div class="text-center mb-6">
          <div class="inline-flex items-center justify-center w-16 h-16 bg-secondary/10 rounded-2xl mb-4">
            <UserPlus class="w-8 h-8 text-secondary" />
          </div>
          <h1 class="text-3xl font-black bg-linear-to-r from-primary to-secondary bg-clip-text text-transparent">Join RotaFive</h1>
          <p class="text-base-content/60 mt-1">Create your account</p>
        </div>

        <!-- Error -->
        <div v-if="error" class="alert alert-error mb-4">
          <AlertCircle class="w-4 h-4" />
          <span>{{ error }}</span>
        </div>

        <!-- Role Selection -->
        <div class="form-control mb-4">
          <label class="label"><span class="label-text font-medium">I am a...</span></label>
          <div class="grid grid-cols-2 gap-3">
            <button type="button" @click="role = 'client'"
              class="btn border-2 transition-all"
              :class="role === 'client' ? 'btn-primary border-primary' : 'btn-ghost border-base-300'">
              <Briefcase class="w-4 h-4" /> Client
            </button>
            <button type="button" @click="role = 'freelancer'"
              class="btn border-2 transition-all"
              :class="role === 'freelancer' ? 'btn-secondary border-secondary' : 'btn-ghost border-base-300'">
              <User class="w-4 h-4" /> Freelancer
            </button>
          </div>
        </div>

        <form @submit.prevent="handleRegister" class="space-y-4">
          <!-- Name (Freelancer only) -->
          <div v-if="role === 'freelancer'" class="form-control">
            <label class="label"><span class="label-text font-medium">Display Name</span></label>
            <label class="input input-bordered flex items-center gap-2">
              <User class="w-4 h-4 opacity-50" />
              <input v-model="name" type="text" placeholder="e.g. Alice Smith" class="grow" />
            </label>
          </div>

          <!-- Skills (Freelancer only) -->
          <div v-if="role === 'freelancer'" class="form-control">
            <label class="label">
              <span class="label-text font-medium">Your Skills</span>
              <span class="label-text-alt text-base-content/50">{{ selectedSkills.length }} selected</span>
            </label>
            <div class="flex flex-wrap gap-2 p-3 bg-base-200 rounded-xl">
              <button
                v-for="skill in allSkills" :key="skill"
                type="button"
                @click="toggleSkill(skill)"
                class="badge cursor-pointer transition-all select-none"
                :class="selectedSkills.includes(skill)
                  ? 'badge-secondary text-white font-bold scale-105'
                  : 'badge-ghost hover:badge-outline'">
                {{ skill }}
              </button>
            </div>
          </div>

          <div class="form-control">
            <label class="label"><span class="label-text font-medium">Email</span></label>
            <label class="input input-bordered flex items-center gap-2">
              <Mail class="w-4 h-4 opacity-50" />
              <input v-model="email" type="email" placeholder="you@example.com" required class="grow" />
            </label>
          </div>

          <div class="form-control">
            <label class="label"><span class="label-text font-medium">Password</span></label>
            <label class="input input-bordered flex items-center gap-2">
              <Lock class="w-4 h-4 opacity-50" />
              <input v-model="password" type="password" placeholder="••••••••" required minlength="6" class="grow" />
            </label>
          </div>

          <button type="submit" class="btn btn-primary w-full mt-2" :disabled="loading">
            <span v-if="loading" class="loading loading-spinner loading-sm"></span>
            <span v-else>Create Account</span>
          </button>
        </form>

        <div class="divider text-base-content/40 text-sm">Already have an account?</div>
        <router-link to="/login" class="btn btn-ghost w-full">Sign In</router-link>
      </div>
    </div>
  </div>
</template>
