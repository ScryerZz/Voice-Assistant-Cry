import platform
import psutil


def get_system_info(*args, **kwargs):
    """
    Возвращает информацию о системе: ОС, процессор, память.
    """
    try:
        os_name = platform.system()
        os_release = platform.release()
        cpu = platform.processor() or "Unknown CPU"
        ram_gb = round(psutil.virtual_memory().total / (1024**3), 2)
        
        ram_used_gb = round(psutil.virtual_memory().used / (1024**3), 2)
        ram_percent = psutil.virtual_memory().percent
        
        result = (
            f"💻 Система:\n"
            f"ОС: {os_name} {os_release}\n"
            f"Процессор: {cpu}\n"
            f"RAM: {ram_used_gb} / {ram_gb} GB ({ram_percent}%)"
        )
        
        return result
    except Exception as e:
        return f"❌ Ошибка получения информации о системе: {e}"


def get_battery_status(*args, **kwargs):
    """
    Возвращает статус батареи (если есть).
    """
    try:
        battery = psutil.sensors_battery()
        
        if not battery:
            return "🔌 Батарея не обнаружена. Устройство работает от сети."
        
        percent = battery.percent
        plugged = "подключено к сети" if battery.power_plugged else "работает от батареи"
        
        # Время до разрядки/зарядки
        if battery.secsleft > 0 and battery.secsleft != psutil.POWER_TIME_UNLIMITED:
            hours = battery.secsleft // 3600
            minutes = (battery.secsleft % 3600) // 60
            time_str = f", осталось {hours}ч {minutes}мин"
        else:
            time_str = ""
        
        return f"🔋 Заряд батареи: {percent}% ({plugged}{time_str})."
    
    except Exception as e:
        return f"❌ Ошибка получения статуса батареи: {e}"

