import { createRouter, createWebHistory } from 'vue-router';
import { store } from './store.js';

import LoginView from './components/LoginView.vue';
import RegisterView from './components/RegisterView.vue';
import HomeView from './components/HomeView.vue';

const routes = [
    {
        path: '/login',
        name: 'Login',
        component: LoginView,
        meta: { guestOnly: true }
    },
    {
        path: '/register',
        name: 'Register',
        component: RegisterView,
        meta: { guestOnly: true }
    },
    {
        path: '/',
        name: 'Home',
        component: HomeView,
        meta: { requiresAuth: true }
    }
];

const router = createRouter({
    history: createWebHistory(),
    routes
});

router.beforeEach((to, from, next) => {
    const isLoggedIn = !!store.token;

    if (to.meta.requiresAuth && !isLoggedIn) {
        return next({ name: 'Login' });
    }

    if (to.meta.guestOnly && isLoggedIn) {
        return next({ name: 'Home' });
    }

    next();
});

export default router;
