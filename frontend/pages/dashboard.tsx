import React, { useState, useEffect, useRef } from "react";
import Head from "next/head";
import { useRouter } from "next/router";
import { 
  FolderLock, 
  BrainCircuit, 
  CalendarDays, 
  ListTodo, 
  LineChart, 
  FileText, 
  LogOut, 
  Upload, 
  Send,
  Plus,
  Trash2,
  Play,
  FileCheck2,
  AlertTriangle,
  Info,
  Sparkles,
  BookOpen,
  CheckCircle,
  HelpCircle,
  HelpCircle as QuestionIcon
} from "lucide-react";
import { api } from "../services/api";

export default function Dashboard() {
  const router = useRouter();
  
  // Auth state
  const [user, setUser] = useState<any>(null);
  
  // Navigation tabs: 'vault', 'chat', 'planner', 'quizzes', 'analytics'
  const [activeTab, setActiveTab] = useState<string>("vault");
  
  // Subject vault states
  const [subjects, setSubjects] = useState<any[]>([]);
  const [activeSubject, setActiveSubject] = useState<any>(null);
  const [showAddSubject, setShowAddSubject] = useState(false);
  const [newSubjectCode, setNewSubjectCode] = useState("");
  const [newSubjectName, setNewSubjectName] = useState("");
  
  // Documents state
  const [documents, setDocuments] = useState<any[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadCategory, setUploadCategory] = useState("notes");
  const [uploading, setUploading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  
  // Chat state
  const [sessions, setSessions] = useState<any[]>([]);
  const [activeSession, setActiveSession] = useState<any>(null);
  const [chatMessages, setChatMessages] = useState<any[]>([]);
  const [newQuery, setNewQuery] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatBottomRef = useRef<HTMLDivElement>(null);
  
  // Study Planner state
  const [activePlan, setActivePlan] = useState<any>(null);
  const [durationDays, setDurationDays] = useState(30);
  const [plannerLoading, setPlannerLoading] = useState(false);
  
  // Quizzes state
  const [quizzes, setQuizzes] = useState<any[]>([]);
  const [activeQuiz, setActiveQuiz] = useState<any>(null);
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, string>>({});
  const [quizGrade, setQuizGrade] = useState<any>(null);
  const [quizLoading, setQuizLoading] = useState(false);
  
  // Analytics state
  const [analytics, setAnalytics] = useState<any>(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);

  // --- INITIAL CHECK ---
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }
    
    // Fetch identity
    api.getCurrentUser()
      .then(u => setUser(u))
      .catch(() => {
        localStorage.removeItem("token");
        router.push("/login");
      });
  }, [router]);

  // --- LOAD SUBJECTS ---
  useEffect(() => {
    if (user) {
      loadSubjects();
    }
  }, [user]);

  const loadSubjects = async () => {
    try {
      const data = await api.listSubjects();
      setSubjects(data);
      if (data.length > 0 && !activeSubject) {
        setActiveSubject(data[0]);
      }
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to load subjects.");
    }
  };

  const handleAddSubject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSubjectCode || !newSubjectName) return;
    try {
      const sub = await api.createSubject({
        code: newSubjectCode,
        name: newSubjectName,
        semester: Number(user?.semester || 6),
        branch: user?.branch || "Computer Engineering"
      });
      setNewSubjectCode("");
      setNewSubjectName("");
      setShowAddSubject(false);
      await loadSubjects();
      setActiveSubject(sub);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to create subject.");
    }
  };

  // --- LOAD TAB CONTEXTS ---
  useEffect(() => {
    if (!activeSubject) return;
    
    // Reset view variables
    setDocuments([]);
    setSessions([]);
    setActiveSession(null);
    setChatMessages([]);
    setActivePlan(null);
    setQuizzes([]);
    setActiveQuiz(null);
    setQuizGrade(null);
    setSelectedAnswers({});
    setAnalytics(null);
    setErrorMsg("");

    if (activeTab === "vault") {
      loadDocuments();
    } else if (activeTab === "chat") {
      loadChatSessions();
    } else if (activeTab === "planner") {
      loadStudyPlan();
    } else if (activeTab === "quizzes") {
      loadQuizzes();
    } else if (activeTab === "analytics") {
      loadAnalytics();
    }
  }, [activeSubject, activeTab]);

  // --- VAULT LOGIC ---
  const loadDocuments = async () => {
    if (!activeSubject) return;
    try {
      const data = await api.listDocuments(activeSubject.id);
      setDocuments(data);
    } catch (err: any) {
      setErrorMsg(err.message);
    }
  };

  const handleFileUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeSubject || !selectedFile) return;
    setUploading(true);
    setErrorMsg("");
    try {
      await api.uploadDocument(activeSubject.id, selectedFile, uploadCategory);
      setSelectedFile(null);
      await loadDocuments();
    } catch (err: any) {
      setErrorMsg(err.message);
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteDocument = async (docId: string) => {
    if (!confirm("Are you sure you want to delete this study document?")) return;
    try {
      await api.deleteDocument(docId);
      await loadDocuments();
    } catch (err: any) {
      setErrorMsg(err.message);
    }
  };

  // --- CHAT LOGIC ---
  const loadChatSessions = async () => {
    if (!activeSubject) return;
    try {
      const data = await api.listChatSessions(activeSubject.id);
      setSessions(data);
      if (data.length > 0) {
        handleSelectSession(data[0]);
      }
    } catch (err: any) {
      setErrorMsg(err.message);
    }
  };

  const handleCreateSession = async () => {
    if (!activeSubject) return;
    const title = prompt("Enter a title for this chat topic:", "Review Loaders");
    if (!title) return;
    try {
      const sess = await api.createChatSession(activeSubject.id, title);
      await loadChatSessions();
      handleSelectSession(sess);
    } catch (err: any) {
      setErrorMsg(err.message);
    }
  };

  const handleSelectSession = async (sess: any) => {
    setActiveSession(sess);
    setChatMessages([]);
    try {
      const history = await api.getChatHistory(sess.id);
      // Map database format to layout bubbles list
      const mapped = history.map((h: any) => ([
        { sender: "user", text: h.query },
        { sender: "assistant", text: h.response, citations: h.citations }
      ])).flat();
      setChatMessages(mapped);
      scrollToChatBottom();
    } catch (err: any) {
      setErrorMsg(err.message);
    }
  };

  const handleSendQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeSession || !newQuery.trim() || chatLoading) return;
    
    const userMsg = newQuery;
    setNewQuery("");
    setChatMessages(prev => [...prev, { sender: "user", text: userMsg }]);
    setChatLoading(true);
    scrollToChatBottom();

    try {
      const ans = await api.sendChatMessage(activeSession.id, userMsg);
      setChatMessages(prev => [...prev, { sender: "assistant", text: ans.response, citations: ans.citations }]);
      scrollToChatBottom();
    } catch (err: any) {
      setErrorMsg(err.message);
    } finally {
      setChatLoading(false);
    }
  };

  const scrollToChatBottom = () => {
    setTimeout(() => {
      chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 50);
  };

  // --- STUDY PLANNER LOGIC ---
  const loadStudyPlan = async () => {
    if (!activeSubject) return;
    setPlannerLoading(true);
    try {
      const plan = await api.getActiveStudyPlan(activeSubject.id);
      setActivePlan(plan);
    } catch (err: any) {
      setActivePlan(null);
    } finally {
      setPlannerLoading(false);
    }
  };

  const handleGeneratePlan = async () => {
    if (!activeSubject) return;
    setPlannerLoading(true);
    try {
      const plan = await api.generateStudyPlan(activeSubject.id, durationDays);
      setActivePlan(plan);
    } catch (err: any) {
      setErrorMsg(err.message);
    } finally {
      setPlannerLoading(false);
    }
  };

  const handleToggleCheckpoint = async (itemId: string, completed: boolean) => {
    if (!activePlan) return;
    try {
      const updated = await api.toggleStudyPlanCheckpoint(activePlan.id, itemId, completed);
      setActivePlan(updated);
    } catch (err: any) {
      setErrorMsg(err.message);
    }
  };

  // --- QUIZZES LOGIC ---
  const loadQuizzes = async () => {
    if (!activeSubject) return;
    setQuizLoading(true);
    try {
      const data = await api.listQuizzes(activeSubject.id);
      setQuizzes(data);
    } catch (err: any) {
      setErrorMsg(err.message);
    } finally {
      setQuizLoading(false);
    }
  };

  const handleGenerateQuiz = async () => {
    if (!activeSubject) return;
    setQuizLoading(true);
    try {
      const qz = await api.generateQuiz(activeSubject.id, `Unit Quiz - ${new Date().toLocaleDateString()}`);
      await loadQuizzes();
      handleSelectQuiz(qz);
    } catch (err: any) {
      setErrorMsg(err.message);
    } finally {
      setQuizLoading(false);
    }
  };

  const handleSelectQuiz = async (qz: any) => {
    setQuizLoading(true);
    setQuizGrade(null);
    setSelectedAnswers({});
    try {
      const details = await api.getQuizDetails(qz.id);
      setActiveQuiz(details);
    } catch (err: any) {
      setErrorMsg(err.message);
    } finally {
      setQuizLoading(false);
    }
  };

  const handleSelectOption = (qid: string, val: string) => {
    setSelectedAnswers(prev => ({ ...prev, [qid]: val }));
  };

  const handleSubmitQuiz = async () => {
    if (!activeQuiz) return;
    setQuizLoading(true);
    try {
      const grade = await api.submitQuizAnswers(activeQuiz.id, selectedAnswers);
      setQuizGrade(grade);
    } catch (err: any) {
      setErrorMsg(err.message);
    } finally {
      setQuizLoading(false);
    }
  };

  // --- ANALYTICS LOGIC ---
  const loadAnalytics = async () => {
    if (!activeSubject) return;
    setAnalyticsLoading(true);
    try {
      const report = await api.getSubjectAnalytics(activeSubject.id);
      setAnalytics(report);
    } catch (err: any) {
      setErrorMsg(err.message);
    } finally {
      setAnalyticsLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    router.push("/login");
  };

  return (
    <>
      <Head>
        <title>Student Learning Dashboard – EduGenAI</title>
      </Head>

      <div className="min-h-screen bg-[#060608] text-slate-100 flex overflow-hidden">
        {/* Navigation Sidebar */}
        <aside className="w-64 bg-[#0a0a0d] border-r border-white/5 flex flex-col shrink-0">
          <div className="p-6 border-b border-white/5 flex items-center space-x-2">
            <BrainCircuit className="h-6 w-6 text-purple-400" />
            <span className="text-lg font-bold tracking-tight bg-gradient-to-r from-purple-400 to-indigo-300 bg-clip-text text-transparent">
              EduGenAI
            </span>
          </div>

          <div className="p-4 border-b border-white/5">
            <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">
              Select Course Subject
            </label>
            <select
              value={activeSubject?.id || ""}
              onChange={(e) => {
                const sub = subjects.find(s => s.id === e.target.value);
                if (sub) setActiveSubject(sub);
              }}
              className="w-full bg-[#111115] border border-white/5 p-2.5 rounded-lg text-sm text-slate-200 outline-none focus:border-purple-500/50 appearance-none"
            >
              {subjects.map((sub) => (
                <option key={sub.id} value={sub.id}>
                  {sub.code}: {sub.name}
                </option>
              ))}
            </select>

            <button
              onClick={() => setShowAddSubject(true)}
              className="w-full mt-3 py-2 bg-white/5 hover:bg-white/10 text-xs font-semibold rounded-lg border border-white/5 flex items-center justify-center space-x-1.5 transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Register Subject</span>
            </button>
          </div>

          <nav className="flex-1 p-4 space-y-1.5 overflow-y-auto">
            {[
              { id: "vault", name: "Subject Vault", icon: FolderLock },
              { id: "chat", name: "AI Study Copilot", icon: BrainCircuit },
              { id: "planner", name: "Study Planner", icon: CalendarDays },
              { id: "quizzes", name: "Practice Quizzes", icon: ListTodo },
              { id: "analytics", name: "Performance Stats", icon: LineChart }
            ].map((tab) => {
              const Icon = tab.icon;
              const active = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all ${
                    active 
                      ? "bg-purple-600/20 text-purple-300 border border-purple-500/30" 
                      : "text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent"
                  }`}
                >
                  <Icon className={`h-4.5 w-4.5 ${active ? "text-purple-400" : ""}`} />
                  <span>{tab.name}</span>
                </button>
              );
            })}
          </nav>

          <div className="p-4 border-t border-white/5 bg-black/20">
            <div className="flex items-center space-x-3 mb-3">
              <div className="h-9 w-9 bg-gradient-to-br from-purple-600 to-indigo-600 rounded-lg flex items-center justify-center text-sm font-bold text-white shadow-md">
                {user?.full_name?.charAt(0).toUpperCase()}
              </div>
              <div className="overflow-hidden">
                <div className="text-xs font-bold truncate">{user?.full_name}</div>
                <div className="text-[10px] text-slate-500 truncate">{user?.branch}</div>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="w-full py-2 border border-red-500/20 text-red-400 text-xs font-semibold rounded-lg hover:bg-red-500/10 flex items-center justify-center space-x-1.5 transition-colors"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span>Log Out</span>
            </button>
          </div>
        </aside>

        {/* Main Content Pane */}
        <main className="flex-1 bg-[#060608] flex flex-col overflow-hidden relative">
          {/* Header */}
          <header className="h-16 border-b border-white/5 px-8 flex items-center justify-between shrink-0 bg-[#0a0a0d]/30 backdrop-blur-sm relative z-20">
            <div>
              {activeSubject ? (
                <div className="flex items-center space-x-2">
                  <span className="text-sm font-bold text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20">
                    {activeSubject.code}
                  </span>
                  <span className="text-sm font-bold text-slate-200">{activeSubject.name}</span>
                </div>
              ) : (
                <span className="text-slate-400 text-sm">Please register a Course Subject to start.</span>
              )}
            </div>

            <div className="text-xs font-semibold text-slate-400">
              Semester {user?.semester} • SPPU Exam Prep
            </div>
          </header>

          {/* Error Banner */}
          {errorMsg && (
            <div className="bg-red-500/10 border-b border-red-500/20 px-8 py-3.5 text-xs text-red-400 flex items-center justify-between shrink-0">
              <div className="flex items-center space-x-2">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                <span>{errorMsg}</span>
              </div>
              <button onClick={() => setErrorMsg("")} className="hover:text-slate-200">Dismiss</button>
            </div>
          )}

          {/* Dynamic Panel Scroll Area */}
          <div className="flex-1 p-8 overflow-y-auto relative z-10">
            {showAddSubject && (
              <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/60 backdrop-blur-sm">
                <div className="w-full max-w-md bg-[#0a0a0d] border border-white/10 rounded-2xl p-6 shadow-2xl relative">
                  <h3 className="text-lg font-bold mb-4">Register New Course Subject</h3>
                  <form onSubmit={handleAddSubject} className="space-y-4">
                    <div>
                      <label className="block text-xs text-slate-400 font-bold uppercase tracking-wider mb-2">Subject Code</label>
                      <input
                        type="text"
                        required
                        placeholder="e.g. CS-334"
                        value={newSubjectCode}
                        onChange={(e) => setNewSubjectCode(e.target.value)}
                        className="w-full bg-[#111115] border border-white/5 p-3 text-sm rounded-xl outline-none text-slate-100 focus:border-purple-500/50"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-slate-400 font-bold uppercase tracking-wider mb-2">Subject Name</label>
                      <input
                        type="text"
                        required
                        placeholder="e.g. System Programming"
                        value={newSubjectName}
                        onChange={(e) => setNewSubjectName(e.target.value)}
                        className="w-full bg-[#111115] border border-white/5 p-3 text-sm rounded-xl outline-none text-slate-100 focus:border-purple-500/50"
                      />
                    </div>
                    <div className="flex space-x-3 pt-2">
                      <button
                        type="submit"
                        className="flex-1 py-3 bg-purple-600 hover:bg-purple-500 text-sm font-semibold rounded-xl text-white transition-colors"
                      >
                        Create
                      </button>
                      <button
                        type="button"
                        onClick={() => setShowAddSubject(false)}
                        className="flex-1 py-3 bg-white/5 hover:bg-white/10 text-sm font-semibold rounded-xl text-slate-300 transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            )}

            {/* TAB CONTENT: SUBJECT VAULT */}
            {activeTab === "vault" && (
              <div className="space-y-8">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                  <div>
                    <h2 className="text-2xl font-bold">Subject Document Vault</h2>
                    <p className="text-sm text-slate-400 mt-1">Upload lecture notes, revision files, or question keys.</p>
                  </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                  {/* Upload Card */}
                  <div className="backdrop-blur-md bg-white/[0.01] border border-white/5 rounded-2xl p-6 h-fit">
                    <h3 className="font-semibold text-sm uppercase tracking-wider text-slate-400 mb-4">Ingest Learning Materials</h3>
                    <form onSubmit={handleFileUpload} className="space-y-4">
                      <div>
                        <label className="block text-xs font-semibold text-slate-400 mb-2">Document Category</label>
                        <select
                          value={uploadCategory}
                          onChange={(e) => setUploadCategory(e.target.value)}
                          className="w-full bg-[#111115] border border-white/5 p-3 rounded-xl text-sm text-slate-200 outline-none"
                        >
                          <option value="notes">Lecture Notes / Slide Packs</option>
                          <option value="pyq">Previous Year Exam Paper (PYQ)</option>
                          <option value="syllabus">Course Syllabus Guide</option>
                        </select>
                      </div>

                      <div className="border border-dashed border-white/10 hover:border-purple-500/40 rounded-xl p-6 text-center cursor-pointer transition-colors relative">
                        <input
                          type="file"
                          required
                          onChange={(e) => {
                            if (e.target.files && e.target.files.length > 0) {
                              setSelectedFile(e.target.files[0]);
                            }
                          }}
                          className="absolute inset-0 opacity-0 cursor-pointer"
                        />
                        <Upload className="h-8 w-8 text-slate-500 mx-auto mb-2" />
                        <span className="block text-xs font-medium text-slate-300">
                          {selectedFile ? selectedFile.name : "Click to select a file (PDF, Docx, PPTX)"}
                        </span>
                      </div>

                      <button
                        type="submit"
                        disabled={uploading || !selectedFile}
                        className="w-full py-3.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-semibold rounded-xl flex items-center justify-center space-x-2 transition-colors disabled:opacity-50"
                      >
                        <span>{uploading ? "Ingesting Document..." : "Upload & Parse"}</span>
                      </button>
                    </form>
                  </div>

                  {/* Documents List */}
                  <div className="lg:col-span-2 backdrop-blur-md bg-white/[0.01] border border-white/5 rounded-2xl p-6">
                    <h3 className="font-semibold text-sm uppercase tracking-wider text-slate-400 mb-4">Ingested Subject Vault Libraries</h3>
                    {documents.length === 0 ? (
                      <div className="py-12 text-center text-slate-500 text-sm">
                        No learning files uploaded in this subject. Ingest a document to activate semantic search indexers.
                      </div>
                    ) : (
                      <div className="divide-y divide-white/5">
                        {documents.map((doc) => (
                          <div key={doc.id} className="py-4 flex items-center justify-between first:pt-0 last:pb-0">
                            <div className="flex items-center space-x-3 overflow-hidden">
                              <div className="p-2 bg-purple-500/10 border border-purple-500/20 rounded-lg text-purple-400">
                                <FileText className="h-5 w-5" />
                              </div>
                              <div className="overflow-hidden">
                                <div className="text-sm font-semibold truncate text-slate-200">{doc.name}</div>
                                <div className="text-[10px] text-slate-500 mt-0.5 uppercase tracking-wider">
                                  Category: {doc.category} • Status:{" "}
                                  <span className={doc.processing_status === "processed" ? "text-emerald-400" : "text-amber-400 animate-pulse"}>
                                    {doc.processing_status}
                                  </span>
                                </div>
                              </div>
                            </div>
                            <button
                              onClick={() => handleDeleteDocument(doc.id)}
                              className="p-2 text-slate-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors shrink-0"
                            >
                              <Trash2 className="h-4.5 w-4.5" />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* TAB CONTENT: CHAT ASSISTANT */}
            {activeTab === "chat" && (
              <div className="h-[calc(100vh-12rem)] flex flex-col overflow-hidden border border-white/5 rounded-2xl bg-white/[0.005]">
                {/* Chat header sessions tabs */}
                <div className="h-14 border-b border-white/5 px-6 flex items-center justify-between bg-black/10 shrink-0">
                  <div className="flex items-center space-x-3 overflow-x-auto py-1">
                    {sessions.map(s => (
                      <button
                        key={s.id}
                        onClick={() => handleSelectSession(s)}
                        className={`text-xs font-semibold px-3 py-1.5 rounded-lg border transition-all ${
                          activeSession?.id === s.id
                            ? "bg-purple-600/10 text-purple-400 border-purple-500/20"
                            : "text-slate-400 border-transparent hover:bg-white/5"
                        }`}
                      >
                        {s.title}
                      </button>
                    ))}
                  </div>
                  <button
                    onClick={handleCreateSession}
                    className="py-1.5 px-3 bg-purple-600 hover:bg-purple-500 text-xs font-bold rounded-lg text-white flex items-center space-x-1 shrink-0"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    <span>New Chat</span>
                  </button>
                </div>

                {/* Messages Panel */}
                <div className="flex-1 p-6 overflow-y-auto space-y-6">
                  {chatMessages.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-500">
                      <Sparkles className="h-8 w-8 text-purple-400 mb-3 animate-pulse" />
                      <p className="text-sm font-semibold">Start an AI copilot session for exam revision.</p>
                      <p className="text-xs text-slate-500 max-w-xs mt-1">Ask questions about loaders, compilers, linkers, or marks allocations.</p>
                    </div>
                  ) : (
                    chatMessages.map((msg, idx) => (
                      <div key={idx} className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"}`}>
                        <div className={`max-w-2xl rounded-2xl p-4 text-sm ${
                          msg.sender === "user"
                            ? "bg-purple-600 text-white rounded-br-none"
                            : "bg-[#0c0c10] border border-white/5 rounded-bl-none text-slate-200"
                        }`}>
                          <div className="leading-relaxed whitespace-pre-wrap">{msg.text}</div>
                          
                          {/* Citations references mapping */}
                          {msg.citations && msg.citations.length > 0 && (
                            <div className="mt-4 pt-3 border-t border-white/5 space-y-2">
                              <div className="text-[10px] text-slate-500 uppercase tracking-widest font-bold flex items-center space-x-1">
                                <Info className="h-3 w-3 text-purple-400" />
                                <span>Study Vault References:</span>
                              </div>
                              <div className="flex flex-wrap gap-2">
                                {msg.citations.map((cit: any, cidx: number) => (
                                  <div key={cidx} className="bg-white/5 border border-white/5 px-2 py-1 rounded text-[10px] text-slate-400 flex items-center space-x-1.5">
                                    <BookOpen className="h-2.5 w-2.5 text-purple-400" />
                                    <span>Page {cit.page} (Category: {cit.category})</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                  {chatLoading && (
                    <div className="flex justify-start">
                      <div className="bg-[#0c0c10] border border-white/5 rounded-2xl rounded-bl-none p-4 max-w-xs flex items-center space-x-3 text-sm text-slate-400">
                        <div className="flex space-x-1 animate-pulse">
                          <span className="h-1.5 w-1.5 bg-purple-400 rounded-full" />
                          <span className="h-1.5 w-1.5 bg-purple-400 rounded-full" />
                          <span className="h-1.5 w-1.5 bg-purple-400 rounded-full" />
                        </div>
                        <span>Copilot is searching vaults...</span>
                      </div>
                    </div>
                  )}
                  <div ref={chatBottomRef} />
                </div>

                {/* Input form */}
                <form onSubmit={handleSendQuery} className="p-4 border-t border-white/5 bg-black/10 shrink-0 flex space-x-3">
                  <input
                    type="text"
                    required
                    disabled={!activeSession || chatLoading}
                    placeholder={activeSession ? "Ask about your notes..." : "Please initialize or select a Chat session first."}
                    value={newQuery}
                    onChange={(e) => setNewQuery(e.target.value)}
                    className="flex-1 bg-[#111115] border border-white/5 p-3 text-sm rounded-xl outline-none text-slate-100 focus:border-purple-500/50"
                  />
                  <button
                    type="submit"
                    disabled={!activeSession || !newQuery.trim() || chatLoading}
                    className="py-3 px-5 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-xl hover:from-purple-500 hover:to-indigo-500 flex items-center justify-center transition-colors disabled:opacity-50 shrink-0"
                  >
                    <Send className="h-4.5 w-4.5" />
                  </button>
                </form>
              </div>
            )}

            {/* TAB CONTENT: STUDY PLANNER */}
            {activeTab === "planner" && (
              <div className="space-y-8">
                <div>
                  <h2 className="text-2xl font-bold">Personalized Study Planner</h2>
                  <p className="text-sm text-slate-400 mt-1">Personalized syllabus scheduler based on document vaults.</p>
                </div>

                {plannerLoading ? (
                  <div className="py-12 text-center text-slate-500 text-sm animate-pulse">
                    Loading planner data...
                  </div>
                ) : !activePlan ? (
                  <div className="backdrop-blur-md bg-white/[0.01] border border-white/5 rounded-2xl p-8 max-w-xl mx-auto text-center">
                    <CalendarDays className="h-10 w-10 text-purple-400 mx-auto mb-4" />
                    <h3 className="text-lg font-bold mb-2">No Active Study Plan</h3>
                    <p className="text-slate-400 text-sm mb-6">
                      Let our StudyPlanner agent partition your exam preparation timelines dynamically based on the syllabus parsed from your uploads.
                    </p>
                    <div className="flex items-center justify-center space-x-4 mb-6">
                      <label className="text-xs text-slate-400 font-semibold uppercase">Duration Plan:</label>
                      <select
                        value={durationDays}
                        onChange={(e) => setDurationDays(Number(e.target.value))}
                        className="bg-[#111115] border border-white/5 px-3 py-1.5 rounded-lg text-sm"
                      >
                        <option value={15}>15 Days (Crash course)</option>
                        <option value={30}>30 Days (Recommended)</option>
                        <option value={45}>45 Days (Thorough revision)</option>
                      </select>
                    </div>
                    <button
                      onClick={handleGeneratePlan}
                      className="py-3 px-6 bg-gradient-to-r from-purple-600 to-indigo-600 text-sm font-semibold rounded-xl text-white hover:scale-[1.02] transition-transform duration-300"
                    >
                      Generate Calendar Plan
                    </button>
                  </div>
                ) : (
                  <div className="backdrop-blur-md bg-white/[0.01] border border-white/5 rounded-2xl p-6 space-y-6">
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-white/5 pb-4">
                      <div>
                        <h3 className="font-semibold text-lg">Active Preparation Calendar</h3>
                        <p className="text-xs text-slate-500 mt-1">
                          Start Date: {new Date(activePlan.start_date).toLocaleDateString()} • End Date: {new Date(activePlan.end_date).toLocaleDateString()}
                        </p>
                      </div>
                      <div className="flex items-center space-x-3">
                        <div className="text-right">
                          <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Overall Progress</div>
                          <div className="text-sm font-bold text-purple-400">{activePlan.schedule.progress_percent}%</div>
                        </div>
                        <div className="w-32 bg-white/5 h-2 rounded-full overflow-hidden border border-white/5">
                          <div className="bg-purple-500 h-full transition-all duration-500" style={{ width: `${activePlan.schedule.progress_percent}%` }} />
                        </div>
                      </div>
                    </div>

                    <div className="space-y-4">
                      {activePlan.schedule.checkpoints.map((chk: any) => (
                        <div 
                          key={chk.id} 
                          className={`p-4 rounded-xl border flex items-center justify-between gap-4 transition-colors ${
                            chk.completed 
                              ? "bg-purple-950/10 border-purple-500/20" 
                              : "bg-[#0c0c10] border-white/5"
                          }`}
                        >
                          <div className="flex items-center space-x-3 overflow-hidden">
                            <input
                              type="checkbox"
                              checked={chk.completed}
                              onChange={(e) => handleToggleCheckpoint(chk.id, e.target.checked)}
                              className="h-4.5 w-4.5 accent-purple-500 cursor-pointer rounded"
                            />
                            <div className="overflow-hidden">
                              <div className={`text-sm font-semibold truncate ${chk.completed ? "text-slate-400 line-through" : "text-slate-200"}`}>
                                {chk.title}
                              </div>
                              <div className="text-[10px] text-slate-500 mt-0.5">
                                Unit: {chk.unit_tag} • Timeline: {chk.days_range}
                              </div>
                            </div>
                          </div>
                          <div className="text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider bg-white/5 text-slate-400 shrink-0">
                            {chk.unit_tag}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* TAB CONTENT: PRACTICE QUIZZES */}
            {activeTab === "quizzes" && (
              <div className="space-y-8">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                  <div>
                    <h2 className="text-2xl font-bold">Interactive Practice Quizzes</h2>
                    <p className="text-sm text-slate-400 mt-1">Generate multiple choice revision worksheets from notes.</p>
                  </div>
                  <button
                    onClick={handleGenerateQuiz}
                    disabled={quizLoading}
                    className="py-2.5 px-4 bg-purple-600 hover:bg-purple-500 text-xs font-bold rounded-lg text-white flex items-center space-x-1.5 shadow-md"
                  >
                    <Plus className="h-4 w-4" />
                    <span>New Quiz</span>
                  </button>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                  {/* Quizzes List Sidebar */}
                  <div className="backdrop-blur-md bg-white/[0.01] border border-white/5 rounded-2xl p-6 h-fit">
                    <h3 className="font-semibold text-xs uppercase tracking-wider text-slate-400 mb-4">Quiz Archives</h3>
                    {quizLoading && quizzes.length === 0 ? (
                      <div className="py-6 text-center text-slate-500 text-xs animate-pulse">Loading list...</div>
                    ) : quizzes.length === 0 ? (
                      <div className="py-6 text-center text-slate-500 text-xs">No practice quizzes generated yet.</div>
                    ) : (
                      <div className="space-y-2">
                        {quizzes.map((qz) => (
                          <button
                            key={qz.id}
                            onClick={() => handleSelectQuiz(qz)}
                            className={`w-full flex items-center justify-between p-3.5 rounded-xl border text-left text-sm transition-all ${
                              activeQuiz?.id === qz.id
                                ? "bg-purple-600/10 border-purple-500/20 text-purple-300"
                                : "bg-[#0c0c10] border-white/5 text-slate-400 hover:text-slate-200"
                            }`}
                          >
                            <div className="overflow-hidden pr-2">
                              <div className="font-bold truncate text-xs">{qz.title}</div>
                              <div className="text-[10px] text-slate-500 mt-0.5">Type: {qz.quiz_type}</div>
                            </div>
                            <Play className="h-3 w-3 shrink-0" />
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Active Quiz Sheet */}
                  <div className="lg:col-span-2 space-y-6">
                    {quizLoading && activeQuiz ? (
                      <div className="backdrop-blur-md bg-white/[0.01] border border-white/5 rounded-2xl p-8 text-center text-slate-500 text-sm animate-pulse">
                        Loading quiz questions details...
                      </div>
                    ) : !activeQuiz ? (
                      <div className="backdrop-blur-md bg-white/[0.01] border border-white/5 rounded-2xl p-8 text-center text-slate-500 text-sm">
                        Select a worksheet from the sidebar archives, or click "New Quiz" to build one dynamically.
                      </div>
                    ) : (
                      <div className="backdrop-blur-md bg-white/[0.01] border border-white/5 rounded-2xl p-6 space-y-8">
                        <div className="flex items-center justify-between border-b border-white/5 pb-4">
                          <div>
                            <h3 className="font-semibold text-lg">{activeQuiz.title}</h3>
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20 uppercase tracking-widest">
                              {activeQuiz.quiz_type} Practice
                            </span>
                          </div>
                        </div>

                        {/* Questions list */}
                        <div className="space-y-8">
                          {activeQuiz.questions_data.questions.map((q: any, qidx: number) => {
                            const gradeFeedback = quizGrade?.feedback?.find((f: any) => f.question_id === q.id);
                            
                            return (
                              <div key={q.id} className="space-y-4">
                                <div className="text-sm font-semibold text-slate-200 flex items-start space-x-2">
                                  <span className="text-purple-400 font-bold">Q{qidx + 1}.</span>
                                  <span>{q.question}</span>
                                </div>

                                {q.choices ? (
                                  /* MCQ Layout */
                                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pl-6">
                                    {Object.entries(q.choices).map(([key, label]: [any, any]) => {
                                      const selected = selectedAnswers[q.id] === key;
                                      const isCorrect = gradeFeedback?.correct_answer === key;
                                      const isWrongSubmitted = gradeFeedback && !gradeFeedback.is_correct && selectedAnswers[q.id] === key;

                                      let optStyle = "bg-[#0c0c10] border-white/5 text-slate-300";
                                      if (selected) optStyle = "bg-purple-600/10 border-purple-500/30 text-purple-300";
                                      if (quizGrade) {
                                        if (isCorrect) optStyle = "bg-emerald-500/10 border-emerald-500/30 text-emerald-300";
                                        else if (isWrongSubmitted) optStyle = "bg-red-500/10 border-red-500/30 text-red-300";
                                      }

                                      return (
                                        <button
                                          key={key}
                                          disabled={!!quizGrade}
                                          onClick={() => handleSelectOption(q.id, key)}
                                          className={`p-3 text-left text-xs rounded-xl border transition-all flex items-center justify-between ${optStyle}`}
                                        >
                                          <span>{key}. {label}</span>
                                          {quizGrade && isCorrect && <CheckCircle className="h-4 w-4 text-emerald-400 shrink-0" />}
                                        </button>
                                      );
                                    })}
                                  </div>
                                ) : (
                                  /* Short Answer Layout */
                                  <div className="pl-6">
                                    <textarea
                                      required
                                      disabled={!!quizGrade}
                                      placeholder="Write your answer description here..."
                                      value={selectedAnswers[q.id] || ""}
                                      onChange={(e) => handleSelectOption(q.id, e.target.value)}
                                      className="w-full bg-[#111115] border border-white/5 p-3.5 text-xs rounded-xl outline-none text-slate-200 focus:border-purple-500/50"
                                      rows={3}
                                    />
                                    {gradeFeedback && (
                                      <div className="mt-3 p-3 bg-white/5 border border-white/5 rounded-lg text-xs space-y-1.5">
                                        <div className="flex items-center space-x-1.5">
                                          <span className="font-bold">Match Status:</span>
                                          <span className={gradeFeedback.is_correct ? "text-emerald-400" : "text-red-400"}>
                                            {gradeFeedback.is_correct ? "Accurate" : "Requires Details"}
                                          </span>
                                        </div>
                                        <div><span className="font-semibold">Matched vocabulary:</span> {gradeFeedback.matched_keywords?.join(", ") || "None"}</div>
                                        <div className="text-slate-400">{gradeFeedback.explanation}</div>
                                      </div>
                                    )}
                                  </div>
                                )}

                                {gradeFeedback && q.choices && (
                                  <div className="pl-6 text-xs text-slate-400 flex items-start space-x-1.5 bg-white/5 border border-white/5 p-3 rounded-lg">
                                    <HelpCircle className="h-4 w-4 text-purple-400 shrink-0" />
                                    <div>
                                      <div className="font-bold text-slate-200">Explanation:</div>
                                      <div className="mt-0.5">{gradeFeedback.explanation}</div>
                                    </div>
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>

                        {quizGrade ? (
                          <div className="p-4 bg-purple-500/10 border border-purple-500/20 rounded-xl flex items-center justify-between">
                            <div>
                              <div className="text-xs font-bold text-slate-400 uppercase">Graded score results</div>
                              <div className="text-lg font-bold text-purple-300 mt-1">
                                {quizGrade.correct_answers} / {quizGrade.total_questions} Correct ({quizGrade.score_percent}%)
                              </div>
                            </div>
                            <button
                              onClick={() => {
                                setQuizGrade(null);
                                setSelectedAnswers({});
                              }}
                              className="py-2 px-4 bg-white/5 hover:bg-white/10 text-xs font-semibold rounded-lg border border-white/5 transition-colors"
                            >
                              Practice Again
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={handleSubmitQuiz}
                            className="w-full py-3.5 bg-gradient-to-r from-purple-600 to-indigo-600 text-white font-semibold rounded-xl hover:from-purple-500 hover:to-indigo-500 transition-colors"
                          >
                            Submit Answers For Grading
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* TAB CONTENT: ANALYTICS DASHBOARD */}
            {activeTab === "analytics" && (
              <div className="space-y-8">
                <div>
                  <h2 className="text-2xl font-bold">Course Performance Stats</h2>
                  <p className="text-sm text-slate-400 mt-1">Calculates study plan checklists completions, uploads metrics, and exam weakness areas.</p>
                </div>

                {analyticsLoading ? (
                  <div className="py-12 text-center text-slate-500 text-sm animate-pulse">Loading dashboard report...</div>
                ) : !analytics ? (
                  <div className="backdrop-blur-md bg-white/[0.01] border border-white/5 rounded-2xl p-8 text-center text-slate-500 text-sm">
                    No analytics reports found. Make sure you upload files, generate a study planner calendar, and practice mock tests to index metrics database tracks.
                  </div>
                ) : (
                  <div className="space-y-8">
                    {/* Metrics Grid */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
                      <div className="backdrop-blur-md bg-white/[0.01] border border-white/5 rounded-2xl p-6">
                        <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Study Checklist Progress</div>
                        <div className="text-2xl font-bold text-purple-400 mt-2">{analytics.study_progress}%</div>
                        <div className="w-full bg-white/5 h-1.5 rounded-full overflow-hidden mt-3 border border-white/5">
                          <div className="bg-purple-500 h-full" style={{ width: `${analytics.study_progress}%` }} />
                        </div>
                      </div>

                      <div className="backdrop-blur-md bg-white/[0.01] border border-white/5 rounded-2xl p-6">
                        <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Mock Tests Completed</div>
                        <div className="text-2xl font-bold text-indigo-400 mt-2">{analytics.total_quizzes_taken} Quizzes</div>
                        <div className="text-[10px] text-slate-500 mt-2 font-medium">Average Score: {analytics.average_quiz_score}%</div>
                      </div>

                      <div className="backdrop-blur-md bg-white/[0.01] border border-white/5 rounded-2xl p-6">
                        <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Essays Evaluated</div>
                        <div className="text-2xl font-bold text-violet-400 mt-2">{analytics.total_essays_evaluated} Submissions</div>
                        <div className="text-[10px] text-slate-500 mt-2 font-medium">Average Mark Score: {analytics.average_essay_score}%</div>
                      </div>

                      <div className="backdrop-blur-md bg-white/[0.01] border border-white/5 rounded-2xl p-6">
                        <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Ingested Archives size</div>
                        <div className="text-2xl font-bold text-slate-200 mt-2">{analytics.total_materials_uploaded} Files</div>
                        <div className="text-[10px] text-slate-500 mt-2 font-medium">Split blocks: {analytics.total_chunks_indexed} chunks</div>
                      </div>
                    </div>

                    {/* Weak Focus Areas Alerts */}
                    <div className="backdrop-blur-md bg-white/[0.01] border border-white/5 rounded-2xl p-6">
                      <h3 className="font-bold text-sm uppercase tracking-wider text-slate-400 mb-4 flex items-center space-x-2">
                        <AlertTriangle className="h-4.5 w-4.5 text-amber-500 shrink-0" />
                        <span>Syllabus Weak Focus Areas</span>
                      </h3>
                      
                      {analytics.weak_units.length === 0 ? (
                        <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs rounded-xl flex items-center space-x-2">
                          <CheckCircle className="h-5 w-5 shrink-0" />
                          <span>Excellent! No syllabus weak focus units detected (under 60% average threshold). Keep reviewing vaults!</span>
                        </div>
                      ) : (
                        <div className="space-y-4">
                          <p className="text-xs text-slate-400">
                            Based on your quiz histories and essay evaluation checkpoints, we have flagged the following units as requiring extra attention:
                          </p>
                          <div className="flex flex-wrap gap-3">
                            {analytics.weak_units.map((unit: string, uidx: number) => (
                              <div key={uidx} className="bg-red-500/10 border border-red-500/20 px-3.5 py-2 rounded-xl text-xs text-red-400 font-bold flex items-center space-x-2">
                                <QuestionIcon className="h-4 w-4 shrink-0" />
                                <span>{unit}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </main>
      </div>
    </>
  );
}
