"""Configuration module for check fraud detection system."""

import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class LLMConfig:
    """LLM provider configuration."""
    provider: str = "groq"
    model: Optional[str] = None
    api_key: Optional[str] = None
    
    # Azure-specific settings
    azure_endpoint: Optional[str] = None
    azure_api_version: str = "2024-02-15-preview"
    azure_deployment: Optional[str] = None
    
    temperature: Optional[float] = 0.1
    max_tokens: int = 4096


@dataclass 
class AnalysisConfig:
    """Configuration for analysis behavior."""
    use_simulation: bool = True
    
    # Tool-specific simulation flags
    simulate_watermark: bool = True
    simulate_signature: bool = True
    simulate_micr: bool = True
    simulate_image_quality: bool = True
    
    # LLM configuration
    llm_config: LLMConfig = field(default_factory=LLMConfig)


def get_config() -> AnalysisConfig:
    """
    Get configuration from environment variables.
    
    Returns:
        AnalysisConfig with settings from environment
    """
    use_simulation_str = os.getenv("USE_SIMULATION", "true").lower()
    use_simulation = use_simulation_str in ("true", "1", "yes")
    
    provider = os.getenv("LLM_PROVIDER", "groq")
    model = os.getenv("LLM_MODEL")
    
    # Get API key based on provider
    if provider == "azure":
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", model)
    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        azure_endpoint = None
        azure_api_version = "2024-02-15-preview"
        azure_deployment = None
    else:  # groq
        api_key = os.getenv("GROQ_API_KEY")
        azure_endpoint = None
        azure_api_version = "2024-02-15-preview"
        azure_deployment = None
    
    llm_config = LLMConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        azure_endpoint=azure_endpoint,
        azure_api_version=azure_api_version,
        azure_deployment=azure_deployment,
    )
    
    return AnalysisConfig(
        use_simulation=use_simulation,
        simulate_watermark=use_simulation,
        simulate_signature=use_simulation,
        simulate_micr=use_simulation,
        simulate_image_quality=use_simulation,
        llm_config=llm_config,
    )


# Global config instance
_config: Optional[AnalysisConfig] = None


def get_analysis_config() -> AnalysisConfig:
    """Get or create the global analysis configuration."""
    global _config
    if _config is None:
        _config = get_config()
    return _config


def set_analysis_config(config: AnalysisConfig) -> None:
    """Set the global analysis configuration."""
    global _config
    _config = config


def reset_config() -> None:
    """Reset configuration to reload from environment."""
    global _config
    _config = None
