#!/usr/bin/python3
import ossapi
import os
import json
import pandas
import sys

# C# MathNet equivalents
import math
import scipy
import scipy.optimize
import numpy

def exit_error():
    print("请重启程序")
    pause()
    sys.exit()

def exit_ok():
    pause()
    sys.exit()

def pause():
    os.system("pause")

def main():

    print("stat-acc pp 计算器（包含 LN 修正），作者：Wafarm")
    print("正在读取配置文件...", end="")

    if not os.path.exists("osu_info.min.json"):
        print("找不到 osu_info.min.json，请确认是否按照 README.txt 操作")
        exit_error()

    osu_info = json.load(open("osu_info.min.json"))
    config = {}

    if not os.path.exists("osu-recalc.json"):
        config = {
            "client_id": None,
            "client_secret": None,
        }
    else:
        config = json.load(open("osu-recalc.json"))

    print("OK")

    if config["client_id"] == None or config["client_secret"] == None:
        print("由于本软件需要调用 osu!api, 在使用前您需先申请 API key")
        print("如果您已有可以直接填入，否则请按下面流程申请")
        print("请使用已登录 osu! 的浏览器打开如下网页")
        print("\thttps://osu.ppy.sh/home/account/edit")
        print("下翻网页找到 \"新的 OAuth 应用\" 按钮，点击并输入如下内容")
        print("\t应用名称：osu-recalc （随便填也行）")
        print("点击 \"注册应用程序\" 按钮，将客户端 ID 和客户端密钥按照提示输入本程序")
        print("本程序不会将您的密钥上传或用作其他用途，仅会在 osu-recalc.json 中存储供下次使用")
        client_id = input("客户端 ID: ")
        client_secret = input("客户端密钥: ")

        try:
            client_id = int(client_id)
        except:
            print("请输入合法的 ID！")
            exit_error()

        config["client_id"] = client_id
        config["client_secret"] = client_secret

    client_id = config["client_id"]
    client_secret = config["client_secret"]

    try:
        print("正在检查 API key 合法性...", end="")
        api = ossapi.Ossapi(client_id, client_secret)
        print("OK")
    except:
        print("API key 无效")
        if os.path.exists("osu-recalc.json"):
            os.remove("osu-recalc.json")
        exit_error()

    json.dump(config, open("osu-recalc.json", "w"))

    username = input("请输入您的 osu! 用户名: ")
    print("正在获取 BP 列表")
    user = api.user(username)
    user_id = user.id
    if user.playmode != "mania":
        print("玩家的默认游戏模式不是 mania，请自行输入玩家的 mania pp: ", end="")
        pp_with_bonus = float(input())
    else:
        pp_with_bonus = user.statistics.pp
    bps = api.user_scores(user_id, "best", limit=100)

    # Calc bonus pp first
    pp = 0
    for idx, bp in enumerate(bps):
        pp += bp.pp * (0.95 ** idx)

    bonus = pp_with_bonus - pp

    print("正在重算")

    # 某些图一根面都没有，取对数为负无穷，我们把这个警告屏蔽掉
    numpy.seterr(divide='ignore')

    new_bp = {
        "beatmap": [],
        "new_sr": [],
        "combo": [],
        "acc": [],
        "est. ur": [],
        "miss": [],
        "mods": [],
        "live pp": [],
        "stat-acc pp": [],
        "pos +/-": [],
        "pp +/-": [],
        "beatmap id": [],
    }
    new_bp = pandas.DataFrame(data=new_bp)

    # print(bps[0])

    tail_multiplier = 1.5
    tail_deviation_multiplier = 1.8

    legacy_max_multiplier = 1.2
    legacy_300_multiplier = 1.1

    for idx, score in enumerate(bps):
        try:
            map_info = osu_info["beatmaps"][str(score.beatmap.id)]
        except:
            print(f"找不到 {score.beatmapset.title}，请阅读 README.txt 进行操作")
            exit_error()
        beatmap_full_name = f"{score.beatmapset.artist} - {score.beatmapset.title} ({score.beatmapset.creator}) [{map_info['difficulty']}]"
        mods = score.mods.short_name()

        if "DT" in mods or "NC" in mods:
            new_sr = map_info["dt_rating"]
        elif "HT" in mods:
            new_sr = map_info["ht_rating"]
        else:
            new_sr = map_info["nm_rating"]
        
        new_sr = round(new_sr, 3)
        
        overallDifficulty = score.beatmap.accuracy

        # Calc hit windows
        hitWindows = [0, 0, 0, 0, 0]
        greatWindowLeniency = 0
        goodWindowLeniency = 0

        windowMultiplier = 1

        if "HR" in mods:
            windowMultiplier *= 1 / 1.4
        elif "EZ" in mods:
            windowMultiplier *= 1.4
        
        hitWindows[0] = math.floor(16 * windowMultiplier)
        hitWindows[1] = math.floor((64 - 3 * overallDifficulty + greatWindowLeniency) * windowMultiplier)
        hitWindows[2] = math.floor((97 - 3 * overallDifficulty + goodWindowLeniency) * windowMultiplier)
        hitWindows[3] = math.floor((127 - 3 * overallDifficulty) * windowMultiplier)
        hitWindows[4] = math.floor((151 - 3 * overallDifficulty) * windowMultiplier)

        note_count = score.beatmap.count_circles
        hold_note_count = score.beatmap.count_sliders
        countPerfect = score.statistics.count_geki
        countGreat = score.statistics.count_300
        countGood = score.statistics.count_katu
        countOk = score.statistics.count_100
        countMeh = score.statistics.count_50
        countMiss = score.statistics.count_miss

        totalJudgements = countPerfect + countOk + countGreat + countGood + countMeh + countMiss

        # Compute estimated UR begin

        note_head_portion = (note_count + hold_note_count) / (note_count + hold_note_count * 2)
        tail_portion = 1 - note_head_portion

        # Cannot find equivalent function in python
        def CDF(mean: float, stddev: float, x: float):
            return 0.5 * math.erfc((mean - x) / (stddev * math.sqrt(2)))

        def PDF(mean: float, stddev: float, x: float):
            d = (x - mean) / stddev
            return math.exp(-0.5 * d * d) / (math.sqrt(2 * math.pi) * stddev)

        def logErfc(x: float):
            if x <= 5:
                return numpy.log(math.erfc(x))
            else:
                return -math.pow(x, 2) - numpy.log(x * math.sqrt(math.pi)) # This is an approximation, https://www.desmos.com/calculator/kdbxwxgf01

        def logDiff(firstLog: float, secondLog: float):
            max_val = max(firstLog, secondLog)

            if max_val == -math.inf:
                return max_val
            
            return firstLog + numpy.log1p(-math.exp(-(firstLog - secondLog)))

        def logSum(firstLog: float, secondLog: float):
            maxVal = max(firstLog, secondLog)
            minVal = min(firstLog, secondLog)

            if maxVal == -math.inf:
                return maxVal
            
            return maxVal + numpy.log(1 + math.exp(minVal - maxVal))

        def logCompProbHitNote(window: float, deviation: float):
            return logErfc(window / (deviation * math.sqrt(2)))
        
        def logCompProbHitLegacyHold(window: float, headDeviation: float, tailDeviation: float):
            root2 = math.sqrt(2)

            logPcHead = logErfc(window / (headDeviation * root2))

            # Calculate the expected value of the distance from 0 of the head hit, given it lands within the current window.
            # We'll subtract this from the tail window to approximate the difficulty of landing both hits within 2x the current window.
            beta = window / headDeviation
            z = CDF(0, 1, beta) - 0.5
            expectedValue = headDeviation * (PDF(0, 1, 0) - PDF(0, 1, beta)) / z

            logPcTail = logErfc((2 * window - expectedValue) / (tailDeviation * root2))

            return logDiff(logSum(logPcHead, logPcTail), logPcHead + logPcTail)
            

        def logJudgementProbsNote(d: float, multiplier: float = 1):
            return {
                "PMax": logDiff(0, logCompProbHitNote(hitWindows[0] * multiplier, d)),
                "P300": logDiff(logCompProbHitNote(hitWindows[0] * multiplier, d), logCompProbHitNote(hitWindows[1] * multiplier, d)),
                "P200": logDiff(logCompProbHitNote(hitWindows[1] * multiplier, d), logCompProbHitNote(hitWindows[2] * multiplier, d)),
                "P100": logDiff(logCompProbHitNote(hitWindows[2] * multiplier, d), logCompProbHitNote(hitWindows[3] * multiplier, d)),
                "P50": logDiff(logCompProbHitNote(hitWindows[3] * multiplier, d), logCompProbHitNote(hitWindows[4] * multiplier, d)),
                "P0": logCompProbHitNote(hitWindows[4] * multiplier, d)
            }

        def logJudgementProbsLegacyHold(dHead: float, dTail: float):
            return {
                "PMax": logDiff(0, logCompProbHitLegacyHold(hitWindows[0] * legacy_max_multiplier, dHead, dTail)),
                "P300": logDiff(logCompProbHitLegacyHold(hitWindows[0] * legacy_max_multiplier, dHead, dTail), logCompProbHitLegacyHold(hitWindows[1] * legacy_300_multiplier, dHead, dTail)),
                "P200": logDiff(logCompProbHitLegacyHold(hitWindows[1] * legacy_300_multiplier, dHead, dTail), logCompProbHitLegacyHold(hitWindows[2], dHead, dTail)),
                "P100": logDiff(logCompProbHitLegacyHold(hitWindows[2], dHead, dTail), logCompProbHitLegacyHold(hitWindows[3], dHead, dTail)),
                "P50": logDiff(logCompProbHitLegacyHold(hitWindows[3], dHead, dTail), logCompProbHitLegacyHold(hitWindows[4], dHead, dTail)),
                "P0": logCompProbHitLegacyHold(hitWindows[4], dHead, dTail)
            }
        
        def calculateLikelihoodOfDeviation(noteProbabilities, lnProbabilities, noteCount, lnCount):
            noteProbCount = noteCount

            pMax = logSum(noteProbabilities["PMax"] + numpy.log(noteProbCount), lnProbabilities["PMax"] + numpy.log(lnCount)) - numpy.log(totalJudgements)
            p300 = logSum(noteProbabilities["P300"] + numpy.log(noteProbCount), lnProbabilities["P300"] + numpy.log(lnCount)) - numpy.log(totalJudgements)
            p200 = logSum(noteProbabilities["P200"] + numpy.log(noteProbCount), lnProbabilities["P200"] + numpy.log(lnCount)) - numpy.log(totalJudgements)
            p100 = logSum(noteProbabilities["P100"] + numpy.log(noteProbCount), lnProbabilities["P100"] + numpy.log(lnCount)) - numpy.log(totalJudgements)
            p50 = logSum(noteProbabilities["P50"] + numpy.log(noteProbCount), lnProbabilities["P50"] + numpy.log(lnCount)) - numpy.log(totalJudgements)
            p0 = logSum(noteProbabilities["P0"] + numpy.log(noteProbCount), lnProbabilities["P0"] + numpy.log(lnCount)) - numpy.log(totalJudgements)
            
            return math.exp(
                (countPerfect * pMax
                + (countGreat + 0.5) * p300
                + countGood * p200
                + countOk * p100
                + countMeh * p50
                + countMiss * p0) / totalJudgements
            )

        def likelihoodGradient(d: float):
            d = d[0]
            if d <= 0:
                return 0
            
            dNote = d / math.sqrt(note_head_portion + tail_portion * math.pow(tail_deviation_multiplier, 2))
            dTail = dNote * tail_deviation_multiplier

            pNotes = logJudgementProbsNote(dNote)
            pHolds = logJudgementProbsLegacyHold(dNote, dTail)

            return -calculateLikelihoodOfDeviation(pNotes, pHolds, note_count, hold_note_count)

        deviation = scipy.optimize.minimize(likelihoodGradient, x0=30, method="Nelder-Mead", tol=1e-6).x[0]
        estimated_ur = deviation * 10

        # Compute estimated UR end

        
        difficulty_value = math.pow(max(new_sr - 0.15, 0.05), 2.2) \
                        * (1 + 0.1 * min(1, (note_count + hold_note_count) / 1500.0)) # Star rating to pp curve

        # We increased the deviation of tails for estimation accuracy, but for difficulty scaling we actually
        # only care about the deviation on notes and heads, as that's the "accuracy skill" of the player.
        # Increasing the tail multiplier will decrease this value, buffing plays with more LNs.
        note_unstable_rate = estimated_ur / math.sqrt(note_head_portion + tail_portion * math.pow(tail_deviation_multiplier, 2))

        multiplier = 8.0

        if "NF" in mods:
            print("No Fail in mods? DERANKER!!!")
            multiplier *= 0.75
        if "EZ" in mods:
            print("Easy in mods? DERANKER!!!")
            multiplier *= 0.5
        

        difficulty_value *= max(1 - math.pow(note_unstable_rate / 500, 1.9), 0)
        pp = round(difficulty_value * multiplier, 3)
        

        new_bp.loc[idx + 1] = [
            beatmap_full_name,
            new_sr,
            score.max_combo,
            score.accuracy * 100,
            estimated_ur,
            score.statistics.count_miss,
            mods,
            score.pp,
            pp,
            0,
            pp - score.pp,
            score.beatmap.id
        ]

    before_sort = new_bp.copy()

    new_bp.sort_values(by=["stat-acc pp"], inplace=True, ascending=False)
    new_bp.reset_index(drop=True, inplace=True)
    new_bp.index += 1

    new_pp = bonus
    # Fill in pos +/- column and calc new pp
    for index, row in new_bp.iterrows():
        old_index = before_sort[before_sort["beatmap id"] == row["beatmap id"]].index[0]
        new_bp.at[index, "pos +/-"] = index - old_index
        new_pp += row["stat-acc pp"] * (0.95 ** (index - 1))

    new_bp.to_csv(f"{username}.csv")

    print("计算完成")
    print(f"旧 pp: {pp_with_bonus}，stat-acc pp: {round(new_pp, 2)} (%+.2fpp)" % round(new_pp - pp_with_bonus, 2))
    print(f"新 BP 列表已输出至 {username}.csv")
    print("注意：该数据可能与 Discord bot 有个位数 pp 的差距，具体原因未知（反正 Unstable Rate 算出来是一样的，不想管了，差的也不多）")

    exit_ok()

if __name__ == "__main__":
    main()
