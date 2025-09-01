// src/context/AuthContext.js
import {createContext, useState, useEffect, useCallback, useMemo} from 'react';
import axios from 'axios';
import {useRouter} from 'next/router';

const AuthContext = createContext();

export const AuthProvider = ({children}) => {
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const logout = useCallback(() => {
    setToken(null);
    localStorage.removeItem('token');
    router.push('/'); // Redirect to the main page, which will show the login form
  }, [router]);

  const apiClient = useMemo(() => {
    const instance = axios.create({
      baseURL: process.env.NEXT_PUBLIC_API_URL,
    });

    // Request Interceptor: Attach the token to every request
    instance.interceptors.request.use(
      config => {
        const storedToken = localStorage.getItem('token');
        if (storedToken) {
          config.headers['Authorization'] = `Bearer ${storedToken}`;
        }
        return config;
      },
      error => Promise.reject(error),
    );

    // Response Interceptor: Check for 401 errors (expired/invalid token)
    instance.interceptors.response.use(
      response => response,
      error => {
        if (error.response && error.response.status === 401) {
          console.log('Authentication error, logging out.');
          logout();
        }
        return Promise.reject(error);
      },
    );

    return instance;
  }, [logout]);

  const login = async (email, password) => {
    try {
      const formData = new URLSearchParams();
      formData.append('username', email);
      formData.append('password', password);

      const response = await apiClient.post('/auth/jwt/login', formData);
      const {access_token} = response.data;

      setToken(access_token);
      localStorage.setItem('token', access_token);
      router.push('/');
      return true;
    } catch (err) {
      console.error('Login failed:', err);
      return false;
    }
  };

  useEffect(() => {
    const storedToken = localStorage.getItem('token');
    if (storedToken) {
      setToken(storedToken);
    }
    setLoading(false);
  }, []);

  return (
    <AuthContext.Provider value={{token, login, logout, loading, apiClient}}>
      {children}
    </AuthContext.Provider>
  );
};

export default AuthContext;
