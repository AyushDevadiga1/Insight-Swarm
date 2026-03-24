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
    if (error.response && error.response.status === 429) {
      throw {
        type: 'RATE_LIMITED',
        ...error.response.data.detail
      };
    }
    throw {
      type: 'SYSTEM_ERROR',
      message: error.response?.data?.detail?.message || error.message
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
