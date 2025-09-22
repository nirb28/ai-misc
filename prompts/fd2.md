Write a detailed prompt for Claude to develop the following:

I am developing an enterprise system that supports inference and other modules. While I am starting with Inference, I want to create the foundation to be modular. The dsp-fd2 is the front door implementation. The front door can take many types of requests. I want to start with inference with openai-compatible implementation. The fd should get the manifest and the module from the control tower () using project/module naming and based on the manifest load the module and make the inference request. Also have the ability to specify the environment to load appropriate urls etc. The modules may contain references to JWT, ai gateway etc. Those reference will be used in the runtime
-----------------------
Claude Opus
----------------------------

Of course. Here is a detailed, structured prompt designed for Claude to help you develop the architecture and implementation plan for your modular enterprise system.

---

### **Prompt for Claude:**

**Objective:** Act as a senior software architect and developer. Your task is to design the core components and outline the implementation strategy for a modular enterprise inference system, starting with an OpenAI-compatible API front door.

#### **1. Context & System Overview**

I am building a new enterprise-grade system designed to be modular from the ground up. The initial module is "Inference," but the architecture must support the seamless addition of future, unrelated modules (e.g., "Data Processing," "Evaluation," "Training").

Built this in:
*   **The Front Door (dsp-fd2):** A gateway service that receives HTTP requests, identifies the target module, and routes the request accordingly.

The system uses other projects:
*   **The Control Tower (dsp-ai-control-tower):** A central service that acts as the source of truth for module configurations and manifests.

*   **JWT (dsp_ai_jwt):** A JWT service that provides tokens for api keys.

*   **RAG Implementation (dsp_ai_rag2):** A RAG devkit that supports a configurable pipeline for RAG usecases.


The core principle is **dynamic discovery and loading**. The Front Door should not have hardcoded logic for specific modules. Instead, it must query the Control Tower to discover how to handle a given request.

#### **2. Core Requirements & Specifications**

**A. Request Flow & Front Door (dsp-fd2) Logic:**
1.  **Receive Request:** The `dsp-fd2` receives an incoming HTTP request.
2.  **Request Analysis:** It must inspect the request to determine:
    *   **Target Project & Module:** This could be via URL path (e.g., `/{project_name}/{module_name}/v1/chat/completions`), a custom header (e.g., `X-Project-Module: project_name/module_name`), or a subdomain (e.g., `{project_name}-{module_name}.api.company.com`). You must recommend the most robust and standard approach.
    *   **Target Environment:** The environment (e.g., `dev`, `staging`, `prod`) must be specifiable, likely via a header (e.g., `X-Environment: staging`) or as part of the project/module name. This is crucial for determining which set of configurations and backend URLs to use.
3.  **Control Tower Query:** Using the identified `project_name`, `module_name`, and `environment`, the `dsp-fd2` queries the Control Tower's API to fetch the **Module Manifest**.
4.  **Manifest Parsing:** The `dsp-fd2` parses the manifest, a JSON/YAML document containing all necessary instructions to load and execute the module.
5.  **Module Execution:** Based on the manifest, the `dsp-fd2` loads the appropriate module code (how this is done is a key part of your design) and proxies the original request to it, injecting any necessary runtime references (see below).
6.  **Response Handling:** The module processes the request, and the `dsp-fd2` relays the response back to the client.

**B. The Module Manifest (from Control Tower):**
The manifest is the contract between the Control Tower and the `dsp-fd2`. For an "inference" module, it must contain:
*   `module_type`: e.g., "inference_openai"
*   `runtime`: e.g., "python:3.11", "nodejs:18", suggesting how the FD should handle it.
*   `endpoint_details`: The actual backend URL(s) for the specified environment (e.g., `dev: "http://internal-dev-inference.svc.cluster.local"`, `prod: "http://internal-llm-proxy.prod.svc"`).
*   `configuration_references`: A list of named references to secrets/configs that the module will need at runtime (e.g., `["jwt_signing_key", "ai_gateway_api_key", "module_specific_secret"]`). The FD will resolve these.
*   `api_schema` (optional): A reference to an OpenAPI spec or a schema defining the expected request/response format for validation.

**C. Runtime Reference Injection:**
The modules themselves should not handle fetching secrets. The `dsp-fd2` must resolve the references named in the `configuration_references` part of the manifest from a secure vault (e.g., HashiCorp Vault, AWS Secrets Manager) and inject them into the module's execution context as environment variables or as a structured config object passed to the module's initialization function.

For example, the manifest has `"jwt_signing_key"`, and the FD fetches the actual secret value for that key and provides it to the module.

**D. Starting with OpenAI Compatibility:**
The first module type, `inference_openai`, must expose an endpoint that is fully compatible with the OpenAI API (e.g., `/v1/chat/completions`). The `dsp-fd2` will route requests to this module, which will then be responsible for translating the request to the backend LLM provider's API (which might also be OpenAI, but could be Anthropic, Cohere, or a self-hosted model) and returning a compatible response.

#### **3. Your Output & Deliverables**

Please provide a detailed response covering the following:

1.  **Recommended Technology Stack:** Justify choices for building the `dsp-fd2` (e.g., Go for robust HTTP handling, Python with FastAPI for simplicity, Java Spring Cloud Gateway) and the module interface (e.g., language-agnostic vs. a specific language with a well-defined SDK).
2.  **High-Level Architecture Diagram:** Describe or create an ASCII art diagram of the request flow, including Client -> `dsp-fd2` -> Control Tower -> Vault -> Module -> Backend LLM.
3.  **Module Interface Contract:** Propose a clear, versioned interface (e.g., a base class, a specific function signature, a gRPC service definition) that all modules must implement. How does the FD load and initialize a module? (e.g., Dynamic import? Sidecar pattern? gRPC client?).
4.  **Manifest Schema:** Provide a detailed, example JSON schema for the Module Manifest returned by the Control Tower for an `inference_openai` module.
5.  **Key Implementation Steps:** Break down the development into phases (e.g., Phase 1: Basic FD routing; Phase 2: Integrate Control Tower; Phase 3: Implement secret injection; Phase 4: Build the first module SDK).
6.  **Security Considerations:** Outline critical security aspects: validating manifests, securing FD->Control Tower communication, secret management, module isolation (sandboxing?), and request authentication/authorization before module execution.
7.  **Scalability & Resilience:** How should the `dsp-fd2` and module loading mechanism be designed to handle failures (Control Tower down, invalid manifest, module load failure) and high traffic?

Focus on creating a clean, extensible foundation rather than optimizing the first inference module. The goal is to get the patterns right for the front door and control tower interaction.
