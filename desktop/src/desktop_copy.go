package main

import "fmt"

const (
	copyStatusConnecting       = "status.connecting"
	copyStatusCheckingRuntime  = "status.checking_runtime"
	copyStatusStartingService  = "status.starting_service"
	copyStatusReady            = "status.ready"
	copyStatusUsingRuntime     = "status.using_runtime"
	copyStatusBackupDatabase   = "status.backup_database"
	copyStatusInstallingUpdate = "status.installing_update"
	copyStatusUpdatingRuntime  = "status.updating_runtime"
	copyStatusFirstExtract     = "status.first_extract"
	copyStatusUpdateFailedKeep = "status.update_failed_keep"
	copyErrorBackupFailed      = "error.backup_failed"
	copyErrorUpgradeFailed     = "error.upgrade_failed"
	copyWait1Minute            = "wait.1_minute"
	copyWaitNMinutes           = "wait.n_minutes"
	copyWait1Second            = "wait.1_second"
	copyWaitNSeconds           = "wait.n_seconds"
	copyHealthNotReady5xx      = "health.not_ready_5xx"
	copyHealthNotReadyConnect  = "health.not_ready_connect"
	copyHealthNotReady         = "health.not_ready"
)

var desktopCopy = map[Locale]map[string]string{
	LocaleEN: {
		copyStatusConnecting:       "Connecting to Artemis…",
		copyStatusCheckingRuntime:  "Checking the runtime…",
		copyStatusStartingService:  "Starting the Artemis service…",
		copyStatusReady:            "Artemis is ready",
		copyStatusUsingRuntime:     "Using the existing runtime…",
		copyStatusBackupDatabase:   "Desktop update %s found. Backing up the database…",
		copyStatusInstallingUpdate: "Installing the bundled desktop update…",
		copyStatusUpdatingRuntime:  "Updating the bundled runtime…",
		copyStatusFirstExtract:     "First launch: unpacking the bundled runtime…",
		copyStatusUpdateFailedKeep: "Runtime update failed; using the existing runtime…",
		copyErrorBackupFailed:      "Database backup failed before upgrade; the current version was preserved",
		copyErrorUpgradeFailed:     "Desktop runtime upgrade failed; the current version was preserved",
		copyWait1Minute:            "1 minute",
		copyWaitNMinutes:           "%d minutes",
		copyWait1Second:            "1 second",
		copyWaitNSeconds:           "%d seconds",
		copyHealthNotReady5xx:      "Artemis did not become ready within %s (%s). The service responded but is not ready yet. Try again, or check the terminal logs.",
		copyHealthNotReadyConnect:  "Artemis did not become ready within %s (%s). Could not connect — make sure Artemis is running.",
		copyHealthNotReady:         "Artemis did not become ready within %s (%s). Make sure Artemis is running at this address, or check the terminal logs.",
	},
	LocaleZH: {
		copyStatusConnecting:       "正在连接 Artemis…",
		copyStatusCheckingRuntime:  "正在检查运行环境…",
		copyStatusStartingService:  "正在启动 Artemis 服务…",
		copyStatusReady:            "Artemis 已就绪",
		copyStatusUsingRuntime:     "正在使用已有运行环境…",
		copyStatusBackupDatabase:   "发现客户端新版 %s，正在备份数据库…",
		copyStatusInstallingUpdate: "正在安装客户端内置新版…",
		copyStatusUpdatingRuntime:  "正在更新内置运行环境…",
		copyStatusFirstExtract:     "首次启动，正在解压内置运行环境…",
		copyStatusUpdateFailedKeep: "更新内置运行环境失败，继续使用已有运行环境…",
		copyErrorBackupFailed:      "升级前数据库备份失败，已保留当前版本",
		copyErrorUpgradeFailed:     "客户端运行环境升级失败，已保留当前版本",
		copyWait1Minute:            "1 分钟",
		copyWaitNMinutes:           "%d 分钟",
		copyWait1Second:            "1 秒",
		copyWaitNSeconds:           "%d 秒",
		copyHealthNotReady5xx:      "Artemis 服务未在%s内就绪（%s）。服务已响应但尚未就绪，请稍后再试，或查看终端日志。",
		copyHealthNotReadyConnect:  "Artemis 服务未在%s内就绪（%s）。目前无法连接该地址，请确认 Artemis 正在运行。",
		copyHealthNotReady:         "Artemis 服务未在%s内就绪（%s）。请确认本机已启动 Artemis，且地址、端口正确；也可查看终端日志。",
	},
}

func desktopText(locale Locale, key string, args ...any) string {
	msg := lookupDesktopCopy(locale, key)
	if len(args) == 0 {
		return msg
	}
	return fmt.Sprintf(msg, args...)
}

func lookupDesktopCopy(locale Locale, key string) string {
	if msgs := desktopCopy[locale]; msgs != nil {
		if msg, ok := msgs[key]; ok {
			return msg
		}
	}
	if msg, ok := desktopCopy[LocaleEN][key]; ok {
		return msg
	}
	return key
}
