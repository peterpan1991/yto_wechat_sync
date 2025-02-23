import random
import re
from threading import Thread
from config import REDIS_CONFIG, MONITORED_GROUPS, PROCESS_TYPE
from logger import logger
from models.redis_queue import RedisQueue
from handlers.wechat_handler import WeChatHandler
from handlers.yto_handler import YtoHandler
from models.order_manager import OrderManager
import time
from datetime import datetime

class MessageBridge:
    def __init__(self):
        self.redis_queue = RedisQueue()
        self.wechat = WeChatHandler(self.redis_queue)
        self.yto = YtoHandler(self.redis_queue)
        self.order_manager = OrderManager(self.redis_queue)
        self.is_running = True
        
        # 重试配置
        self.max_retries = 3
        self.retry_delay = 5  # 秒

    def init(self) -> bool:
        """初始化所有组件"""
        if not self.wechat.init_wx():
            return False
        if not self.yto.init_browser():
            return False
        return True

    def process(self):
        while self.is_running:
            try:
                groups = self.wechat.get_groups_to_handle()
                if not groups:
                    # logger.warning("没有需要处理的群")
                    time.sleep(1)
                    continue

                for id, group in groups.items():
                    group_name = re.sub(r'\d+条新消息$', '', group.Name)
                    logger.info(f"处理群: {group.Name}, {id}")
                    wechat_messages = self.wechat.handle_group_message(id, group)
                    for msg in wechat_messages:
                        if not msg.content:
                            continue
                        
                        # 提取订单号并注册关联
                        order_numbers = self.order_manager.extract_order_number(msg.content)
                        if not order_numbers:
                            continue
                        
                        self.order_manager.register_order(order_numbers, msg.session_id)
                        logger.info(f"从群 {msg.session_id} 提取到订单号: {order_numbers}")
                        
                        # 发送消息到圆通
                        self.yto.send_message(msg.content)

                        # 获取圆通消息
                        order_count = len(order_numbers)
                        retry_count = 0
                        send_times = 0
                        max_while_times = 20
                        while_times = 0
                        content = ""
                        while True:
                            time.sleep(1)
                            while_times += 1                            
                            yto_messages = self.yto.handle_yto_message()
                            is_send = False
                            for yto_msg in yto_messages:
                                if not yto_msg.content:
                                    continue

                                yto_order_numbers = self.order_manager.extract_order_number(yto_msg.content)
                                if not yto_order_numbers or yto_order_numbers[0] not in order_numbers:
                                    continue

                                # 将消息发送到微信
                                content = content + yto_msg.content + "\n"
                                is_send = True
                                send_times += 1
                                
                            if not is_send:
                                retry_count += 1
                            
                            logger.info(f"获取圆通消息循环次数: {retry_count}, 发送次数: {send_times}")
                            
                            if retry_count >= self.max_retries or send_times >= order_count:
                                if content:
                                    self.wechat.send_message(content, msg.session_id, group_name)
                                break
                                
                            if while_times >= max_while_times:
                                break
                            
                    time.sleep(random.uniform(1, 1.5))
                time.sleep(random.uniform(0.5, 1))
            except Exception as e:
                logger.error(f"执行出错: {e}")
                self.is_running = False

    def run(self):        

        """运行消息桥接服务"""
        if not self.init():
            logger.error("初始化失败，程序退出")
            return               

        time.sleep(10)

        # 启动处理线程
        process_thread = Thread(target=self.process)
        process_thread.start()

        try:
            while self.is_running:
                # 获取当前时间
                now = datetime.now()
                # 检查是否达到晚上23点
                if now.hour == 23 and now.minute >= 59:
                    logger.info("到达晚上23点59分，正在关闭...")
                    
                time.sleep(120)

                self.yto.login()

                time.sleep(10)
        except KeyboardInterrupt:
            logger.info("接收到退出信号，正在关闭...")
            self.is_running = False

        process_thread.join()

        logger.info("程序已退出")

