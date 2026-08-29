import axios from 'axios';

const api = axios.create({
  baseURL: '', // Proxied by Vite in dev
  headers: {
    'Content-Type': 'application/json',
  },
});

export const verifyClaim = async (claim) => {
  try {
    const response = await api.post('/verify', { claim });
    return response.data;
  } catch (error) {
    const detail = error.response?.data?.detail;
    if (error.response && error.response.status === 429) {
      const base = { type: 'RATE_LIMITED', retry_after: 60 };
      throw typeof detail === 'object' && detail !== null
        ? { ...base, ...detail }
        : { ...base, message: detail ?? error.message };
    }
    throw {
      type: 'SYSTEM_ERROR',
      message: (typeof detail === 'object' && detail !== null && detail.message) || error.message
    };
  }
};

export const submitFeedback = async (claim, verdict, value) => {
  try {
    await api.post('/feedback', { claim, verdict, value });
    return true;
  } catch (error) {
    console.error('Feedback failed:', error);
    return false;
  }
};

export default api;
