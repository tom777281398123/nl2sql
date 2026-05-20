from typing import Optional

from langchain_huggingface import HuggingFaceEndpointEmbeddings

from app.conf.app_config import EmbeddingConfig, app_config


class EmbeddingClientManager:
    def __init__(self, config: EmbeddingConfig):
        self.client: Optional[HuggingFaceEndpointEmbeddings] = None
        self.config = config

    def _get_url(self):
        return f"http://{self.config.host}:{self.config.port}"

    def init(self):
        self.client = HuggingFaceEndpointEmbeddings(model=self._get_url())

    def verify(self) -> bool:
        """
        验证嵌入服务是否正常工作
        
        Returns:
            bool: 如果服务正常返回 True，否则返回 False
        """
        try:
            if self.client is None:
                raise RuntimeError("Embedding client not initialized")
            
            test_text = "测试文本"
            embedding = self.client.embed_query(test_text)
            
            if embedding is None:
                raise RuntimeError("Failed to generate embedding")
            
            if len(embedding) == 0:
                raise RuntimeError("Empty embedding returned")
            
            print(f"✓ Embedding service verified successfully")
            print(f"  - Test text: {test_text}")
            print(f"  - Embedding dimension: {len(embedding)}")
            print(f"  - Sample values: {embedding[:3]}")
            
            return True
            
        except Exception as e:
            print(f"✗ Embedding service verification failed: {str(e)}")
            return False


embedding_client_manager = EmbeddingClientManager(app_config.embedding)

"""
嵌入服务验证脚本
用于测试 EmbeddingClientManager 是否正常工作
"""
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.clients.embedding_client_manager import embedding_client_manager


def verify_embedding_service():
    """验证嵌入服务"""
    print("=" * 60)
    print("Embedding Service Verification")
    print("=" * 60)

    print("\n1. Initializing embedding client...")
    try:
        embedding_client_manager.init()
        print("   ✓ Client initialized successfully")
    except Exception as e:
        print(f"   ✗ Failed to initialize client: {e}")
        return False

    print("\n2. Verifying embedding service...")
    is_valid = embedding_client_manager.verify()

    if is_valid:
        print("\n" + "=" * 60)
        print("Verification Result: PASSED ✓")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("Verification Result: FAILED ✗")
        print("=" * 60)

    return is_valid


if __name__ == "__main__":
    success = verify_embedding_service()
    sys.exit(0 if success else 1)