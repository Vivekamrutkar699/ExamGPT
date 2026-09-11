const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function getHeaders(isMultipart = false) {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers: HeadersInit = {};
  
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  
  if (!isMultipart) {
    headers["Content-Type"] = "application/json";
  }
  
  return headers;
}

async function handleResponse(response: Response) {
  if (response.status === 204) {
    return null;
  }
  
  const data = await response.json();
  
  if (!response.ok) {
    throw new Error(data.detail || "Something went wrong");
  }
  
  return data;
}

export const api = {
  // --- AUTH ---
  async login(credentials: any) {
    const res = await fetch(`${BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        username: credentials.email,
        password: credentials.password
      })
    });
    const data = await handleResponse(res);
    if (data && data.access_token) {
      localStorage.setItem("token", data.access_token);
    }
    return data;
  },

  async register(studentData: any) {
    const res = await fetch(`${BASE_URL}/auth/register`, {
      method: "POST",
      headers: getHeaders(),
      body: JSON.stringify(studentData)
    });
    return handleResponse(res);
  },

  async getCurrentUser() {
    const res = await fetch(`${BASE_URL}/auth/me`, {
      method: "GET",
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  // --- SUBJECTS ---
  async listSubjects() {
    const res = await fetch(`${BASE_URL}/documents/subjects`, {
      method: "GET",
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  async createSubject(subject: any) {
    const res = await fetch(`${BASE_URL}/documents/subjects`, {
      method: "POST",
      headers: getHeaders(),
      body: JSON.stringify(subject)
    });
    return handleResponse(res);
  },

  // --- DOCUMENTS ---
  async uploadDocument(subjectId: string, file: File, category: string) {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("category", category);

    const res = await fetch(`${BASE_URL}/documents/upload/${subjectId}`, {
      method: "POST",
      headers: getHeaders(true),
      body: formData
    });
    return handleResponse(res);
  },

  async listDocuments(subjectId: string) {
    const res = await fetch(`${BASE_URL}/documents/subject/${subjectId}`, {
      method: "GET",
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  async deleteDocument(docId: string) {
    const res = await fetch(`${BASE_URL}/documents/${docId}`, {
      method: "DELETE",
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  // --- CHAT SYSTEM ---
  async listChatSessions(subjectId: string) {
    const res = await fetch(`${BASE_URL}/chats/sessions/subject/${subjectId}`, {
      method: "GET",
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  async createChatSession(subjectId: string, title: string) {
    const res = await fetch(`${BASE_URL}/chats/sessions`, {
      method: "POST",
      headers: getHeaders(),
      body: JSON.stringify({ subject_id: subjectId, title })
    });
    return handleResponse(res);
  },

  async getChatHistory(sessionId: string) {
    const res = await fetch(`${BASE_URL}/chats/sessions/${sessionId}/history`, {
      method: "GET",
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  async sendChatMessage(sessionId: string, message: string) {
    const res = await fetch(`${BASE_URL}/chats/sessions/${sessionId}/query`, {
      method: "POST",
      headers: getHeaders(),
      body: JSON.stringify({ query: message })
    });
    return handleResponse(res);
  },

  // --- STUDY PLANNER ---
  async getActiveStudyPlan(subjectId: string) {
    const res = await fetch(`${BASE_URL}/study-plans/subject/${subjectId}`, {
      method: "GET",
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  async generateStudyPlan(subjectId: string, durationDays: number) {
    const res = await fetch(`${BASE_URL}/study-plans/`, {
      method: "POST",
      headers: getHeaders(),
      body: JSON.stringify({ subject_id: subjectId, days_duration: durationDays })
    });
    return handleResponse(res);
  },

  async toggleStudyPlanCheckpoint(planId: string, itemId: string, completed: boolean) {
    const res = await fetch(`${BASE_URL}/study-plans/${planId}/checkpoint`, {
      method: "PUT",
      headers: getHeaders(),
      body: JSON.stringify({ item_id: itemId, completed })
    });
    return handleResponse(res);
  },

  // --- MOCK QUIZZES ---
  async listQuizzes(subjectId: string) {
    const res = await fetch(`${BASE_URL}/quizzes/subject/${subjectId}`, {
      method: "GET",
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  async generateQuiz(subjectId: string, title: string, quizType = "MCQ") {
    const res = await fetch(`${BASE_URL}/quizzes/`, {
      method: "POST",
      headers: getHeaders(),
      body: JSON.stringify({ subject_id: subjectId, title, quiz_type: quizType })
    });
    return handleResponse(res);
  },

  async getQuizDetails(quizId: string) {
    const res = await fetch(`${BASE_URL}/quizzes/${quizId}`, {
      method: "GET",
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  async submitQuizAnswers(quizId: string, answers: Record<string, string>) {
    const res = await fetch(`${BASE_URL}/quizzes/${quizId}/submit`, {
      method: "POST",
      headers: getHeaders(),
      body: JSON.stringify({ answers })
    });
    return handleResponse(res);
  },

  // --- ESSAY ANSWERS EVALUATION ---
  async evaluateEssay(questionId: string, answer: string) {
    const res = await fetch(`${BASE_URL}/evaluations/`, {
      method: "POST",
      headers: getHeaders(),
      body: JSON.stringify({ question_id: questionId, user_submitted_answer: answer })
    });
    return handleResponse(res);
  },

  async listEvaluations(subjectId: string) {
    const res = await fetch(`${BASE_URL}/evaluations/subject/${subjectId}`, {
      method: "GET",
      headers: getHeaders()
    });
    return handleResponse(res);
  },

  // --- ANALYTICS DASHBOARD ---
  async getSubjectAnalytics(subjectId: string) {
    const res = await fetch(`${BASE_URL}/analytics/subjects/${subjectId}`, {
      method: "GET",
      headers: getHeaders()
    });
    return handleResponse(res);
  }
};
