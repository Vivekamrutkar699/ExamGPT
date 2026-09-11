import React from "react";
import Head from "next/head";
import Link from "next/link";
import { 
  BookOpen, 
  Cpu, 
  FileText, 
  BrainCircuit, 
  TrendingUp, 
  CheckCircle, 
  Sparkles, 
  ArrowRight,
  Shield,
  Layers,
  FileCheck2
} from "lucide-react";

export default function Home() {
  return (
    <>
      <Head>
        <title>EduGenAI – AI-Powered SPPU Exam Intelligence Platform</title>
      </Head>

      <div className="relative min-h-screen bg-[#0a0a0c] text-slate-100 overflow-x-hidden">
        {/* Decorative background glow elements */}
        <div className="absolute top-[-10%] left-[-10%] w-[500px] h-[500px] rounded-full bg-purple-900/10 blur-[120px] pointer-events-none" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[500px] h-[500px] rounded-full bg-indigo-900/10 blur-[120px] pointer-events-none" />

        {/* Navigation Bar */}
        <nav className="sticky top-0 z-50 backdrop-blur-md border-b border-white/5 bg-[#0a0a0c]/80 px-6 py-4 transition-all duration-300">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className="p-2 bg-purple-600/20 border border-purple-500/30 rounded-lg">
                <BrainCircuit className="h-6 w-6 text-purple-400" />
              </div>
              <span className="text-xl font-bold tracking-tight bg-gradient-to-r from-purple-400 to-indigo-300 bg-clip-text text-transparent">
                EduGenAI
              </span>
            </div>

            <div className="hidden md:flex items-center space-x-8 text-sm font-medium text-slate-400">
              <a href="#features" className="hover:text-purple-400 transition-colors">Features</a>
              <a href="#pipeline" className="hover:text-purple-400 transition-colors">Document Pipeline</a>
              <a href="#agents" className="hover:text-purple-400 transition-colors">AI Agents</a>
            </div>

            <div className="flex items-center space-x-4">
              <Link 
                href="/login" 
                className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white transition-colors"
              >
                Sign In
              </Link>
              <Link 
                href="/register" 
                className="px-4 py-2 text-sm font-medium bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white rounded-lg border border-purple-500/20 shadow-[0_0_15px_rgba(147,51,234,0.15)] hover:shadow-[0_0_20px_rgba(147,51,234,0.25)] transition-all duration-300"
              >
                Register Now
              </Link>
            </div>
          </div>
        </nav>

        {/* Hero Section */}
        <section className="relative pt-20 pb-24 px-6 max-w-7xl mx-auto text-center">
          <div className="inline-flex items-center space-x-2 px-3 py-1.5 rounded-full border border-purple-500/20 bg-purple-500/5 text-purple-400 text-xs font-semibold tracking-wider uppercase mb-8 animate-pulse">
            <Sparkles className="h-3.5 w-3.5" />
            <span>AI-Powered SPPU Preparation</span>
          </div>

          <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight mb-6 max-w-4xl mx-auto leading-tight">
            Elevate Your SPPU Exam prep with{" "}
            <span className="bg-gradient-to-r from-purple-400 via-violet-400 to-indigo-300 bg-clip-text text-transparent">
              Intelligence
            </span>
          </h1>

          <p className="text-lg md:text-xl text-slate-400 max-w-2xl mx-auto mb-10 leading-relaxed">
            Upload notes, lecture slides, and past papers. Let our LangGraph multi-agent orchestrator build study plans, analyze trends, generate solutions, and grade your answers.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
            <Link 
              href="/register" 
              className="w-full sm:w-auto px-8 py-4 font-semibold text-white bg-gradient-to-r from-purple-600 to-indigo-600 rounded-xl hover:scale-105 transition-transform duration-300 flex items-center justify-center space-x-2 shadow-[0_0_30px_rgba(147,51,234,0.3)]"
            >
              <span>Get Started Free</span>
              <ArrowRight className="h-5 w-5" />
            </Link>
            <a 
              href="#features" 
              className="w-full sm:w-auto px-8 py-4 font-semibold text-slate-300 bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 hover:text-white transition-all duration-300 flex items-center justify-center"
            >
              Learn More
            </a>
          </div>

          {/* Core Feature Cards Dashboard Preview Grid */}
          <div id="features" className="grid grid-cols-1 md:grid-cols-3 gap-8 text-left mt-24">
            <div className="group p-8 rounded-2xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.04] transition-all duration-300 hover:border-purple-500/20">
              <div className="p-3 bg-purple-500/10 border border-purple-500/20 rounded-xl w-fit mb-6 text-purple-400 group-hover:scale-110 transition-transform duration-300">
                <BookOpen className="h-6 w-6" />
              </div>
              <h3 className="text-xl font-bold mb-3 group-hover:text-purple-300 transition-colors">Smart Subject Vaults</h3>
              <p className="text-slate-400 text-sm leading-relaxed">
                Organize learning materials by Semester, Branch, and Subject. Feed documents directly into dedicated semantic vector layers.
              </p>
            </div>

            <div className="group p-8 rounded-2xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.04] transition-all duration-300 hover:border-indigo-500/20">
              <div className="p-3 bg-indigo-500/10 border border-indigo-500/20 rounded-xl w-fit mb-6 text-indigo-400 group-hover:scale-110 transition-transform duration-300">
                <BrainCircuit className="h-6 w-6" />
              </div>
              <h3 className="text-xl font-bold mb-3 group-hover:text-indigo-300 transition-colors">LangGraph AI Agents</h3>
              <p className="text-slate-400 text-sm leading-relaxed">
                Collaborative specialized agents analyze patterns, predict focus areas, and evaluate student responses against target marks structure.
              </p>
            </div>

            <div className="group p-8 rounded-2xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.04] transition-all duration-300 hover:border-violet-500/20">
              <div className="p-3 bg-violet-500/10 border border-violet-500/20 rounded-xl w-fit mb-6 text-violet-400 group-hover:scale-110 transition-transform duration-300">
                <FileCheck2 className="h-6 w-6" />
              </div>
              <h3 className="text-xl font-bold mb-3 group-hover:text-violet-300 transition-colors">Answer Evaluation</h3>
              <p className="text-slate-400 text-sm leading-relaxed">
                Submit raw handwritten notes or typed answers. AI details missed points, checks SPPU format accuracy, and awards marks.
              </p>
            </div>
          </div>
        </section>

        {/* Feature 2: Document Pipeline Visual Representation */}
        <section id="pipeline" className="border-t border-white/5 bg-white/[0.01] py-24 px-6">
          <div className="max-w-7xl mx-auto">
            <div className="text-center mb-16">
              <h2 className="text-3xl md:text-4xl font-bold mb-4">The Intelligent Parsing Pipeline</h2>
              <p className="text-slate-400 max-w-xl mx-auto">
                Documents are parsed semantically through multi-stage processing, avoiding naive split rules to maintain complete engineering context.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-5 gap-4 relative">
              {[
                { step: "01", name: "Multi-Format Ingestion", desc: "PDF, Word, PPTX, image or scanned note support." },
                { step: "02", name: "Layout & OCR Extraction", desc: "PaddleOCR layout detection for structural identification." },
                { step: "03", name: "Semantic Chunking", desc: "Chunk boundaries are split dynamically based on topic shifts." },
                { step: "04", name: "Metadata Labeling", desc: "Tagging with Semester, Subject, Unit & PYQ marks." },
                { step: "05", name: "Hybrid DB Vector Storage", desc: "Dense/sparse storage setup for exact matching retrieval." },
              ].map((pipe, idx) => (
                <div key={idx} className="relative p-6 rounded-xl border border-white/5 bg-slate-900/50 backdrop-blur-sm">
                  <div className="text-xs font-bold text-purple-400 mb-2">{pipe.step}</div>
                  <h4 className="font-semibold mb-2 text-white text-sm">{pipe.name}</h4>
                  <p className="text-slate-400 text-xs leading-relaxed">{pipe.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer className="border-t border-white/5 py-12 px-6 bg-black/40">
          <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center space-x-2">
              <BrainCircuit className="h-5 w-5 text-purple-400" />
              <span className="text-sm font-semibold tracking-tight text-white">EduGenAI Platform</span>
            </div>
            <p className="text-slate-500 text-xs">
              © {new Date().getFullYear()} EduGenAI. Prepared for SPPU Academic Excellence.
            </p>
            <div className="flex space-x-6 text-xs text-slate-500">
              <a href="#" className="hover:text-slate-300">Privacy Policy</a>
              <a href="#" className="hover:text-slate-300">Terms of Service</a>
            </div>
          </div>
        </footer>
      </div>
    </>
  );
}
