# RAG Generation + Grounding Benchmark Report

- **Evaluation Scope**: Production RAG retrieval and Ollama generation evaluated on the frozen 35-case benchmark corpus.
- **Dataset**: SPPU Engineering Core Evaluation Dataset (v1.0.0)
- **Corpus Version**: 1.0.0
- **Model**: `llama3.2:3b`
- **Temperature**: `0.2` | **Max Tokens**: `800`
- **Timestamp**: `2026-09-14T14:42:53.878950+00:00`
- **Total Cases**: 35

## Aggregate Metrics

| Metric | Score | Notes |
| :--- | :---: | :--- |
| **Generation Success Rate** | **100.0%** | 35/35 completed without error |
| **Mean Concept Coverage** | **0.9429** | Proportion of syllabus concepts present in answer |
| **Mean Grounded Concept Coverage** | **0.9314** | Context-overlap proxy (concepts in both context & answer) |
| **Mean Citation Validity** | **0.0857** | Parsed citations referencing valid source indices (1..k) |
| **Mean Citation Source Match** | **0.0857** | Cited page numbers matching chunk metadata |
| **Confidence Compliance Rate** | **14.3%** | Answers containing valid `Confidence:` indicator |

> [!NOTE]
> **Grounded Concept Coverage** is a deterministic lexical/context overlap proxy and does NOT represent full semantic faithfulness.

## Per-Subject Metrics

| Subject | Cases | Success Rate | Concept Coverage | Grounded Coverage | Citation Validity | Citation Match | Confidence Compliance |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **CN** | 8 | 100.0% | 0.9250 | 0.9000 | 0.1250 | 0.1250 | 0.0% |
| **DBMS** | 6 | 100.0% | 1.0000 | 1.0000 | 0.1667 | 0.1667 | 0.0% |
| **SPOS** | 16 | 100.0% | 0.9125 | 0.9125 | 0.0000 | 0.0000 | 18.8% |
| **TOC** | 5 | 100.0% | 1.0000 | 0.9600 | 0.2000 | 0.2000 | 40.0% |

## Failure Analysis (35 cases with deficiencies)

Criteria for flag: generation error, concept coverage < 0.5, grounded coverage < 0.5, citation validity < 1.0, citation page mismatch, or confidence compliance = 0.

### 1. [eval_spos_001] (SPOS Unit 1)
- **Question**: What is the difference between a linker and a loader in system programming?
- **Metrics**: Concept Cov: `1.00` | Grounded Cov: `1.00` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `1.0`
- **Retrieved Chunks**: `['chunk_spos_u1_001', 'chunk_spos_u1_002', 'chunk_spos_u3_003', 'chunk_spos_u1_004']`
- **Answer Snippet**: "**Difference between Linker and Loader** =====================================  In system programming, a **Linker** and a **Loader** are two distinct systems programs that play crucial roles in the ex..."

### 2. [eval_spos_002] (SPOS Unit 1)
- **Question**: Explain relocation in loaders and how memory addresses are adjusted.
- **Metrics**: Concept Cov: `0.80` | Grounded Cov: `0.80` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `1.0`
- **Retrieved Chunks**: `['chunk_spos_u1_002', 'chunk_spos_u1_001', 'chunk_spos_u5_001', 'chunk_spos_u3_003']`
- **Answer Snippet**: "**Relocation in Loaders and Address Adjustment** =====================================================  **What is Relocation?** ------------------------  Relocation in loaders refers to the process of..."

### 3. [eval_spos_003] (SPOS Unit 1)
- **Question**: What databases are used by a macro processor during Pass 1 and Pass 2?
- **Metrics**: Concept Cov: `1.00` | Grounded Cov: `1.00` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `0.0`
- **Retrieved Chunks**: `['chunk_spos_u1_003', 'chunk_spos_u1_004', 'chunk_dbms_u4_001', 'chunk_spos_u2_001']`
- **Answer Snippet**: "**Databases Used by Macro Processor**  During Pass 1 and Pass 2 of macro processing, the Macro Processor uses the following databases:  ### **Pass 1: Macro Definitions**  *   **Macro Name Table (MNT)*..."

### 4. [eval_spos_004] (SPOS Unit 1)
- **Question**: Compare macros and subroutines in terms of code size and execution overhead...
- **Metrics**: Concept Cov: `0.80` | Grounded Cov: `0.80` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `0.0`
- **Retrieved Chunks**: `['chunk_spos_u1_004', 'chunk_spos_u1_003', 'chunk_spos_u2_001', 'chunk_spos_u2_002']`
- **Answer Snippet**: "**Comparison of Macros and Subroutines** =====================================  ### Code Size  *   **Macros**: Macros expand into a sequence of assembly language instructions, which increases the exec..."

### 5. [eval_spos_005] (SPOS Unit 2)
- **Question**: List and explain the different phases of a compiler from source to target c...
- **Metrics**: Concept Cov: `1.00` | Grounded Cov: `1.00` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `0.0`
- **Retrieved Chunks**: `['chunk_spos_u2_001', 'chunk_spos_u1_003', 'chunk_spos_u2_002', 'chunk_spos_u1_004']`
- **Answer Snippet**: "**Phases of a Compiler** ==========================  A compiler undergoes several phases to transform the source code into target machine code. The following are the different phases of a compiler:  #..."

### 6. [eval_spos_006] (SPOS Unit 2)
- **Question**: What is the role of a lexical analyzer or scanner in compilation?
- **Metrics**: Concept Cov: `0.80` | Grounded Cov: `0.80` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `0.0`
- **Retrieved Chunks**: `['chunk_spos_u2_002', 'chunk_spos_u2_001', 'chunk_spos_u1_001', 'chunk_spos_u1_002']`
- **Answer Snippet**: "**Role of a Lexical Analyzer (Scanner) in Compilation** ===========================================================  The Lexical Analyzer (Scanner) plays a crucial role in the compilation process. Its..."

### 7. [eval_spos_007] (SPOS Unit 2)
- **Question**: Differentiate between top-down parsing and bottom-up parsing techniques.
- **Metrics**: Concept Cov: `0.80` | Grounded Cov: `0.80` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `0.0`
- **Retrieved Chunks**: `['chunk_spos_u2_003', 'chunk_spos_u2_001', 'chunk_spos_u1_004', 'chunk_spos_u2_002']`
- **Answer Snippet**: "**Top-Down Parsing vs Bottom-Up Parsing** =====================================  **Overview** ------------  Parsing is a crucial step in compiler design that involves breaking down the source code int..."

### 8. [eval_spos_008] (SPOS Unit 3)
- **Question**: What information is stored inside a Process Control Block (PCB)?
- **Metrics**: Concept Cov: `0.80` | Grounded Cov: `0.80` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `0.0`
- **Retrieved Chunks**: `['chunk_spos_u3_001', 'chunk_spos_u3_003', 'chunk_spos_u1_002', 'chunk_dbms_u4_001']`
- **Answer Snippet**: "**Process Control Block (PCB) Contents** =====================================  A Process Control Block (PCB) contains the following information:  *   **Process State**: The current state of the proce..."

### 9. [eval_spos_009] (SPOS Unit 3)
- **Question**: Compare CPU scheduling algorithms FCFS, SJF, and Round Robin.
- **Metrics**: Concept Cov: `1.00` | Grounded Cov: `1.00` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `1.0`
- **Retrieved Chunks**: `['chunk_spos_u3_002', 'chunk_spos_u6_001', 'chunk_spos_u5_002', 'chunk_spos_u4_002']`
- **Answer Snippet**: "**CPU Scheduling Algorithms Comparison** =====================================  ### Overview  This section compares three CPU scheduling algorithms: First-Come, First-Served (FCFS), Shortest Job First..."

### 10. [eval_spos_010] (SPOS Unit 3)
- **Question**: Explain inter-process communication (IPC) using shared memory and message p...
- **Metrics**: Concept Cov: `0.60` | Grounded Cov: `0.60` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `0.0`
- **Retrieved Chunks**: `['chunk_spos_u3_003', 'chunk_spos_u3_001', 'chunk_spos_u1_002', 'chunk_spos_u4_001']`
- **Answer Snippet**: "**Inter-Process Communication (IPC) Mechanisms** =====================================================  IPC mechanisms enable processes to exchange data and synchronize with each other. Two common IPC..."

### 11. [eval_spos_011] (SPOS Unit 4)
- **Question**: State the three requirements to solve the critical section problem in proce...
- **Metrics**: Concept Cov: `1.00` | Grounded Cov: `1.00` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `0.0`
- **Retrieved Chunks**: `['chunk_spos_u4_001', 'chunk_spos_u3_001', 'chunk_spos_u4_003', 'chunk_spos_u3_003']`
- **Answer Snippet**: "**Critical Section Problem Requirements** =============================================  To solve the Critical Section Problem in process synchronization, the following three requirements must be sati..."

### 12. [eval_spos_012] (SPOS Unit 4)
- **Question**: What are the four Coffman conditions necessary for a deadlock to occur?
- **Metrics**: Concept Cov: `1.00` | Grounded Cov: `1.00` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `0.0`
- **Retrieved Chunks**: `['chunk_spos_u4_002', 'chunk_spos_u4_003', 'chunk_cn_u2_002', 'chunk_spos_u1_003']`
- **Answer Snippet**: "**Deadlock Conditions**  To determine if a deadlock situation has occurred, we need to check if all four Coffman conditions are met simultaneously.  The four Coffman conditions are:  1. **Mutual Exclu..."

### 13. [eval_spos_013] (SPOS Unit 4)
- **Question**: How does Banker's algorithm achieve deadlock avoidance using safe state tes...
- **Metrics**: Concept Cov: `1.00` | Grounded Cov: `1.00` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `0.0`
- **Retrieved Chunks**: `['chunk_spos_u4_003', 'chunk_spos_u4_002', 'chunk_spos_u3_002', 'chunk_spos_u4_001']`
- **Answer Snippet**: "**Banker's Algorithm for Deadlock Avoidance** =============================================  **Overview** ------------  Banker's Algorithm is a deadlock avoidance technique that uses a set of data str..."

### 14. [eval_spos_014] (SPOS Unit 5)
- **Question**: Explain paging in memory management and the role of the TLB.
- **Metrics**: Concept Cov: `1.00` | Grounded Cov: `1.00` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `0.0`
- **Retrieved Chunks**: `['chunk_spos_u5_001', 'chunk_spos_u3_001', 'chunk_spos_u3_003', 'chunk_spos_u1_002']`
- **Answer Snippet**: "**Paging in Memory Management** ================================  Paging is a memory management scheme that eliminates external fragmentation by partitioning physical memory into fixed-size frames and..."

### 15. [eval_spos_015] (SPOS Unit 5)
- **Question**: Compare FIFO, LRU, and Optimal page replacement algorithms and Belady's ano...
- **Metrics**: Concept Cov: `1.00` | Grounded Cov: `1.00` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `0.0`
- **Retrieved Chunks**: `['chunk_spos_u5_002', 'chunk_spos_u3_002', 'chunk_spos_u6_001', 'chunk_spos_u5_001']`
- **Answer Snippet**: "**Page Replacement Algorithms Comparison** =====================================  ### Overview  This section compares three popular page replacement algorithms: FIFO, LRU, and Optimal. We also discuss..."

### 16. [eval_spos_016] (SPOS Unit 6)
- **Question**: Explain disk scheduling algorithms SSTF and SCAN for minimizing head seek t...
- **Metrics**: Concept Cov: `1.00` | Grounded Cov: `1.00` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `0.0`
- **Retrieved Chunks**: `['chunk_spos_u6_001', 'chunk_spos_u3_002', 'chunk_spos_u5_002', 'chunk_spos_u4_002']`
- **Answer Snippet**: "**Disk Scheduling Algorithms: SSTF and SCAN**  **Overview** -----------  Disk scheduling algorithms are used to optimize the movement of the disk read/write head to minimize seek time. Two popular alg..."

### 17. [eval_cn_001] (CN Unit 1)
- **Question**: Explain the 7 layers of the OSI reference model and compare with TCP/IP mod...
- **Metrics**: Concept Cov: `1.00` | Grounded Cov: `1.00` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `0.0`
- **Retrieved Chunks**: `['chunk_cn_u1_001', 'chunk_cn_u5_001', 'chunk_cn_u4_001', 'chunk_cn_u3_001']`
- **Answer Snippet**: "**7 Layers of the OSI Reference Model**  The OSI (Open Systems Interconnection) 7-layer reference model is a conceptual framework used to understand how data is transmitted over a network. The layers ..."

### 18. [eval_cn_002] (CN Unit 1)
- **Question**: Compare star network topology and mesh network topology in terms of fault t...
- **Metrics**: Concept Cov: `1.00` | Grounded Cov: `1.00` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `0.0`
- **Retrieved Chunks**: `['chunk_cn_u1_002', 'chunk_cn_u1_001', 'chunk_cn_u3_002', 'chunk_spos_u5_002']`
- **Answer Snippet**: "**Comparison of Star and Mesh Network Topologies in Terms of Fault Tolerance**  | **Topology** | **Fault Tolerance** | **Description** | | --- | --- | --- | | **Star** | Low | In a star topology, all ..."

### 19. [eval_cn_003] (CN Unit 2)
- **Question**: How does Cyclic Redundancy Check (CRC) detect transmission errors in data l...
- **Metrics**: Concept Cov: `1.00` | Grounded Cov: `1.00` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `0.0`
- **Retrieved Chunks**: `['chunk_cn_u2_001', 'chunk_cn_u2_002', 'chunk_cn_u1_002', 'chunk_spos_u3_003']`
- **Answer Snippet**: "**Cyclic Redundancy Check (CRC) Error Detection** =====================================================  CRC is a widely used error detection technique in data link frames. Here's how it works:  **Ste..."

### 20. [eval_cn_004] (CN Unit 2)
- **Question**: Compare Go-Back-N and Selective Repeat sliding window ARQ protocols.
- **Metrics**: Concept Cov: `0.80` | Grounded Cov: `0.80` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `0.0`
- **Retrieved Chunks**: `['chunk_cn_u2_002', 'chunk_cn_u4_001', 'chunk_cn_u3_002', 'chunk_cn_u5_001']`
- **Answer Snippet**: "**Comparison of Go-Back-N and Selective Repeat Sliding Window ARQ Protocols** ====================================================================  **Overview** ------------  Sliding Window ARQ (Autom..."

### 21. [eval_cn_005] (CN Unit 3)
- **Question**: Explain IPv4 classful addressing vs CIDR subnetting and subnet masks.
- **Metrics**: Concept Cov: `1.00` | Grounded Cov: `0.80` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `0.0`
- **Retrieved Chunks**: `['chunk_cn_u3_001', 'chunk_cn_u1_001', 'chunk_cn_u5_001', 'chunk_cn_u4_001']`
- **Answer Snippet**: "**IPv4 Classful Addressing vs CIDR Subnetting and Subnet Masks**  ### Classful Addressing  Classful addressing divides 32-bit IPv4 addresses into five classes:  | Class | Number of Hosts | Subnet Mask..."

### 22. [eval_cn_006] (CN Unit 3)
- **Question**: Compare Distance Vector Routing and Link State Routing algorithms.
- **Metrics**: Concept Cov: `1.00` | Grounded Cov: `1.00` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `0.0`
- **Retrieved Chunks**: `['chunk_cn_u3_002', 'chunk_spos_u6_001', 'chunk_cn_u1_001', 'chunk_spos_u3_002']`
- **Answer Snippet**: "**Comparison of Distance Vector Routing and Link State Routing Algorithms** ====================================================================  **Overview** ------------  Distance Vector Routing (DV..."

### 23. [eval_cn_007] (CN Unit 4)
- **Question**: What are the main differences between TCP and UDP protocols?
- **Metrics**: Concept Cov: `0.80` | Grounded Cov: `0.80` | Cit Validity: `1.00` | Cit Match: `1.00` | Conf Compliance: `0.0`
- **Retrieved Chunks**: `['chunk_cn_u5_001', 'chunk_cn_u1_001', 'chunk_cn_u4_001', 'chunk_spos_u1_004']`
- **Answer Snippet**: "**TCP vs UDP: Key Differences** =====================================  The main differences between TCP (Transmission Control Protocol) and UDP (User Datagram Protocol) are:  ### 1. Connection Orienta..."

### 24. [eval_cn_008] (CN Unit 5)
- **Question**: Explain the role of DNS and DHCP protocols in the application layer.
- **Metrics**: Concept Cov: `0.80` | Grounded Cov: `0.80` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `0.0`
- **Retrieved Chunks**: `['chunk_cn_u5_001', 'chunk_cn_u1_001', 'chunk_cn_u4_001', 'chunk_spos_u3_003']`
- **Answer Snippet**: "**Application Layer Protocols: DNS and DHCP**  The Application Layer is the topmost layer of the OSI 7-Layer Reference Model and the TCP/IP Model. It provides services and interfaces for end-user appl..."

### 25. [eval_dbms_001] (DBMS Unit 1)
- **Question**: Explain the Three-Schema Architecture of a database management system.
- **Metrics**: Concept Cov: `1.00` | Grounded Cov: `1.00` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `0.0`
- **Retrieved Chunks**: `['chunk_dbms_u1_001', 'chunk_dbms_u4_001', 'chunk_spos_u2_001', 'chunk_spos_u1_001']`
- **Answer Snippet**: "**Three-Schema Architecture of a Database Management System** ===========================================================  The Three-Schema Architecture is a fundamental concept in Database Management..."

### 26. [eval_dbms_002] (DBMS Unit 1)
- **Question**: Describe the components of an Entity-Relationship (ER) diagram.
- **Metrics**: Concept Cov: `1.00` | Grounded Cov: `1.00` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `0.0`
- **Retrieved Chunks**: `['chunk_dbms_u1_002', 'chunk_dbms_u1_001', 'chunk_dbms_u2_001', 'chunk_dbms_u4_001']`
- **Answer Snippet**: "**Components of an Entity-Relationship (ER) Diagram** =====================================================  An Entity-Relationship (ER) diagram is a visual representation of the structure of a databa..."

### 27. [eval_dbms_003] (DBMS Unit 2)
- **Question**: What are the fundamental operations in relational algebra?
- **Metrics**: Concept Cov: `1.00` | Grounded Cov: `1.00` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `0.0`
- **Retrieved Chunks**: `['chunk_dbms_u2_001', 'chunk_dbms_u4_001', 'chunk_toc_u3_001', 'chunk_spos_u2_001']`
- **Answer Snippet**: "**Fundamental Operations in Relational Algebra** =====================================================  Relational algebra is a mathematical notation for manipulating relational databases. The fundame..."

### 28. [eval_dbms_004] (DBMS Unit 3)
- **Question**: Explain 1NF, 2NF, 3NF, and BCNF normal forms in database normalization.
- **Metrics**: Concept Cov: `1.00` | Grounded Cov: `1.00` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `0.0`
- **Retrieved Chunks**: `['chunk_dbms_u3_001', 'chunk_toc_u3_001', 'chunk_dbms_u1_001', 'chunk_dbms_u4_001']`
- **Answer Snippet**: "**Database Normalization: Normal Forms** =====================================  Database normalization is the process of organizing the data in a database to minimize data redundancy and dependency. T..."

### 29. [eval_dbms_005] (DBMS Unit 4)
- **Question**: Explain the ACID properties of a database transaction.
- **Metrics**: Concept Cov: `1.00` | Grounded Cov: `1.00` | Cit Validity: `1.00` | Cit Match: `1.00` | Conf Compliance: `0.0`
- **Retrieved Chunks**: `['chunk_dbms_u4_001', 'chunk_dbms_u1_001', 'chunk_dbms_u3_001', 'chunk_dbms_u4_002']`
- **Answer Snippet**: "**ACID Properties of Database Transactions** =============================================  A database transaction is a sequence of operations that are executed as a single, all-or-nothing unit. The A..."

### 30. [eval_dbms_006] (DBMS Unit 4)
- **Question**: How does Two-Phase Locking (2PL) guarantee serializability in transactions?
- **Metrics**: Concept Cov: `1.00` | Grounded Cov: `1.00` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `0.0`
- **Retrieved Chunks**: `['chunk_dbms_u4_002', 'chunk_dbms_u4_001', 'chunk_cn_u1_002', 'chunk_spos_u4_002']`
- **Answer Snippet**: "**Two-Phase Locking (2PL) Serializability Guarantee**  Two-Phase Locking (2PL) is a concurrency control technique that ensures serializability in transactions. Serializability is a property of a concu..."

### 31. [eval_toc_001] (TOC Unit 1)
- **Question**: Compare Deterministic Finite Automata (DFA) and Non-deterministic Finite Au...
- **Metrics**: Concept Cov: `1.00` | Grounded Cov: `1.00` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `1.0`
- **Retrieved Chunks**: `['chunk_toc_u1_001', 'chunk_toc_u3_001', 'chunk_spos_u2_002', 'chunk_toc_u1_002']`
- **Answer Snippet**: "**Comparison of Deterministic Finite Automata (DFA) and Non-deterministic Finite Automata (NFA)**  ### Overview  Deterministic Finite Automata (DFA) and Non-deterministic Finite Automata (NFA) are two..."

### 32. [eval_toc_002] (TOC Unit 1)
- **Question**: What is the difference between Moore machines and Mealy machines?
- **Metrics**: Concept Cov: `1.00` | Grounded Cov: `1.00` | Cit Validity: `1.00` | Cit Match: `1.00` | Conf Compliance: `0.0`
- **Retrieved Chunks**: `['chunk_toc_u1_002', 'chunk_toc_u4_001', 'chunk_spos_u1_004', 'chunk_spos_u5_001']`
- **Answer Snippet**: "**Differences between Moore Machines and Mealy Machines**  Moore Machines and Mealy Machines are both types of finite state machines with output capabilities. The main difference between them lies in ..."

### 33. [eval_toc_003] (TOC Unit 2)
- **Question**: State the Pumping Lemma for regular languages and explain how it is used.
- **Metrics**: Concept Cov: `1.00` | Grounded Cov: `0.80` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `0.0`
- **Retrieved Chunks**: `['chunk_toc_u2_001', 'chunk_spos_u2_002', 'chunk_spos_u3_001', 'chunk_toc_u3_001']`
- **Answer Snippet**: "**Pumping Lemma for Regular Languages**  The Pumping Lemma states that any sufficiently long string `w` in a regular language can be split into three parts: `w = xyz`, satisfying the following conditi..."

### 34. [eval_toc_004] (TOC Unit 3)
- **Question**: Explain Context-Free Grammars (CFG) and Pushdown Automata (PDA).
- **Metrics**: Concept Cov: `1.00` | Grounded Cov: `1.00` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `1.0`
- **Retrieved Chunks**: `['chunk_toc_u3_001', 'chunk_spos_u2_002', 'chunk_spos_u3_001', 'chunk_toc_u1_001']`
- **Answer Snippet**: "**Context-Free Grammars (CFG) and Pushdown Automata (PDA)** ===========================================================  **Context-Free Grammars (CFG)** -----------------------------  A Context-Free G..."

### 35. [eval_toc_005] (TOC Unit 4)
- **Question**: Describe a Turing Machine and explain why the Halting Problem is undecidabl...
- **Metrics**: Concept Cov: `1.00` | Grounded Cov: `1.00` | Cit Validity: `0.00` | Cit Match: `0.00` | Conf Compliance: `0.0`
- **Retrieved Chunks**: `['chunk_toc_u4_001', 'chunk_toc_u1_002', 'chunk_spos_u4_001', 'chunk_spos_u1_002']`
- **Answer Snippet**: "**Turing Machine Description** ================================  A Turing Machine (TM) is a mathematical model for computation that consists of the following components:  *   **Infinite Tape**: A tape..."

