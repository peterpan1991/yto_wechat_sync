import random
from selenium import webdriver
from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
# from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from logger import logger
from models.message import Message
from models.message import MessageSource
from typing import Any, Optional, Dict, List
from models.redis_queue import RedisQueue
from collections import deque
import time
import re
from config import YTO_MESSAGE_FORMATS, YTO_SERVICE_ID, NEW_YTO_MESSAGE_COUNT, ORDER_FORMAT
from selenium.common.exceptions import NoSuchElementException

class YtoHandler:
    def __init__(self, redis_queue):
        self.driver = None
        self.max_processed_count = 10
        self.buffer = deque(maxlen=self.max_processed_count)
        self.current_session_id = None
        self.redis_queue = redis_queue
        
    def init_browser(self):
        """初始化浏览器"""
        try:
            # 打开浏览器的调试端口
            # chrome --remote-debugging-port=9222

            # 连接到已打开的浏览器
            options = Options()
            options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
            self.driver = webdriver.Chrome(options=options)

            # self.monitor_new_message()
            logger.info("浏览器初始化成功")
            return True
        except Exception as e:
            logger.error(f"初始化浏览器失败: {e}")
            raise  # 重新抛出异常
	
    def monitor_new_message(self):
        script = """
		var newItems = []; // 用于存储新增条目

		var targetNode = document.querySelector('#msgContentRef');
		var config = { childList: true, subtree: true };

		var callback = function(mutationsList) {
			mutationsList.forEach(mutation => {
                console.log("test", mutation.type, mutation.addedNodes.length);
				if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
					mutation.addedNodes.forEach(node => {
						if (node.nodeType === 1) { // 确保是元素节点
							newItems.push(node); // 保存新条目
						}
					});
				}
			});
		};

		var observer = new MutationObserver(callback);
		observer.observe(targetNode, config);

		// 提供一个方法来获取新条目
		window.getNewItems = function() {
			var items = newItems.slice(); // 复制新增条目
			newItems.length = 0; // 清空列表
			return items;
		};


		// 观察器将持续工作，直到显式调用 observer.disconnect()
		"""

		# 在页面中执行脚本
        self.driver.execute_script(script)

    def is_valid_message(self, msg: str) -> bool:
        """过滤消息"""
        # 过滤掉不符合规则的消息
        patterns = YTO_MESSAGE_FORMATS
        for pattern in patterns:
            match = re.search(pattern, msg, re.DOTALL)
            if match:
                return True
        return False
    
    def format_message(self, msg:str) -> str:
        """格式化消息"""
        msg = msg.replace("客服潘", "")
        if re.search(r"人工", msg):
            match = re.search(ORDER_FORMAT[0], msg)
            order_number = '无有效订单'
            if match:
                order_number = match.group()  # 获取匹配的订单号
            if re.search(r"已存在有效拦截", msg):
                return f"{order_number}, 已存在有效拦截"
            else:
                return f"{order_number}, 您稍等[玫瑰][玫瑰][玫瑰]"

        else:
            return msg
    
    def close_dialog(self):
        """关闭弹窗"""
        try:
            dialog_close_buttons = self.driver.find_elements(By.CSS_SELECTOR, 'button[aria-label="Close"]')
            for button in dialog_close_buttons:
                if button.is_displayed() and button.is_enabled():
                    button.click()
                    break
            else:
                return False
        except Exception as e:
            logger.error(f"关闭弹窗失败: {e}")
            raise  # 重新抛出异常
    
    def send_message(self, message: str) -> bool:
        """发送消息到圆通系统"""
        try:
            # # 找到消息输入框
            # 判断页面是否有弹窗
            self.close_dialog()

            # 
            message_input = self.driver.find_element(By.ID, "edit-content")
            # 清除输入框，输入框不是input或textarea元素，而是div，contenteditable="true"
            message_input.send_keys(Keys.CONTROL + "a")  # 全选
            message_input.send_keys(Keys.DELETE)
            # 使用 execute_script 方法将消息插入到输入框中
            self.driver.execute_script("arguments[0].innerText = arguments[1];", message_input, message)
            # time.sleep(random.uniform(0.5, 1.5))
            message_input.send_keys(Keys.ENTER)
            # # 输入消息 换行符会被截断
            # message_input.send_keys(message)
                    
            # # 点击发送按钮
            send_button = self.driver.find_element(By.CLASS_NAME, "send-btn")
            send_button.click()
            
            logger.info(f"消息已发送到圆通系统: {message}")
            return True
            
        except Exception as e:
            logger.error(f"发送消息到圆通系统失败: {e}")
            raise  # 重新抛出异常
    
    def handle_yto_message(self) -> List[Message]:
        """尝试获取并处理消息，带重试机制"""
        try:
            # 关闭页面弹窗
            self.close_dialog()
            
            message_elements = self.driver.find_elements(By.CSS_SELECTOR, ".news-box")

            #获取最后几条，避免数据过多，数据被顶掉
            last_news_message_elements = message_elements[-NEW_YTO_MESSAGE_COUNT:]
            
            # last_news_message_elements = self.driver.execute_script("return window.getNewItems();")

            messages = []
            for msg_item in last_news_message_elements:
                    # msg_item = new_msg_item.find_element(By.CSS_SELECTOR, ".news-box")

                    # 获取消息信息
                    first_div = msg_item.find_element(By.XPATH, "./div[1]")
                    sender_span = first_div.find_element(By.XPATH, "./span[1]") # 获取发送者
                    send_time_span = first_div.find_element(By.XPATH, "./span[2]") # 获取时间
                    script = "return arguments[0].innerText;"
                    send_time = self.driver.execute_script(script, send_time_span)
                    msg_content = msg_item.find_element(By.CSS_SELECTOR, ".text-content").text                    

                    if(sender_span.text != YTO_SERVICE_ID):
                        # logger.info(f"收到来自 {sender_span.text} 的消息: {msg_content}")
                        continue
                    
                    if self.is_valid_message(msg_content):
                        msg_content = self.format_message(msg_content)
                        # 如果消息未处理过，添加到缓冲区
                        if msg_content and self.redis_queue.is_message_in_yto_processed_queue(msg_content) is False:
                            self.redis_queue.put_yto_processed_message(msg_content)
                            message = Message(
								content=msg_content,
								source=MessageSource.YTO,
								# session_id=self.current_session_id
							)
                            messages.append(message)
                            # self.current_session_id = session_id
                            logger.info(f"获取到yto消息: {msg_content}")
            
            return messages
        except Exception as e:
            logger.error(f"获取圆通消息失败: {e}")
            raise  # 重新抛出异常
