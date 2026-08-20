"""economics 模块单元测试（纯函数，无需 agentsociety2 / 网络）。

运行：python -m unittest discover -s tests -v
"""

import unittest

from agri_sandbox.economics import (
    DEFAULT_CROPS,
    GRAINS,
    EconomicsParams,
    FarmerAccounting,
    compute_farmer_accounting,
    village_summary,
)


class TestEconomicsParams(unittest.TestCase):
    def test_defaults(self):
        p = EconomicsParams()
        self.assertIn("wheat", p.crops)
        self.assertIn("rice", GRAINS)
        self.assertGreater(p.rent_in_per_mu, 0)
        self.assertLess(p.disaster_threshold, 0)

    def test_from_file_roundtrip(self):
        p = EconomicsParams()
        d = p.to_dict()
        # to_dict 的 list 形式再进 from_file 应无异常（字段结构一致即可）
        self.assertIn("crops", d)
        self.assertEqual(len(d["crops"]), len(DEFAULT_CROPS))


class TestComputeAccounting(unittest.TestCase):
    def setUp(self):
        self.policy = {
            "subsidy_per_mu": {"wheat": 120.0},
            "insurance_subsidy_rate": 0.0,
            "land_transfer_out_subsidy_per_mu": 0.0,
            "grain_price_support": 0.0,
        }
        self.params = EconomicsParams()

    def test_basic_wheat_farming(self):
        # 10 亩小麦，正常年景、无价格冲击
        acct = compute_farmer_accounting(
            plan={"wheat": 10.0},
            insured={},
            transfer_in_mu=0.0,
            transfer_out_mu=0.0,
            policy=self.policy,
            price_shock={},
            weather_shock=0.0,
            off_farm_income_annual=0.0,
            params=self.params,
        )
        spec = self.params.crops["wheat"]
        expect_gross = spec["yield"] * 10.0 * spec["price"]
        self.assertAlmostEqual(acct.gross_revenue, expect_gross, places=6)
        self.assertAlmostEqual(acct.total_cost, spec["cost"] * 10.0, places=6)
        # 补贴 = 120 元/亩 × 10 亩
        self.assertAlmostEqual(acct.subsidy_income, 1200.0, places=6)
        self.assertAlmostEqual(acct.planted_area_mu, 10.0)
        self.assertIsInstance(acct, FarmerAccounting)

    def test_subsidy_and_price_support(self):
        policy = dict(self.policy)
        policy["subsidy_per_mu"] = {"corn": 100.0}
        policy["grain_price_support"] = 50.0  # 玉米在主粮集合内
        acct = compute_farmer_accounting(
            plan={"corn": 5.0},
            insured={},
            transfer_in_mu=0.0,
            transfer_out_mu=0.0,
            policy=policy,
            price_shock={},
            weather_shock=0.0,
            params=self.params,
        )
        # 补贴 = 面积×(直补 + 粮价支持) = 5×(100+50)
        self.assertAlmostEqual(acct.subsidy_income, 750.0, places=6)

    def test_insurance_payout_on_disaster(self):
        # 投保 5 亩水稻，灾害年景触发赔付
        acct = compute_farmer_accounting(
            plan={"rice": 5.0},
            insured={"rice": 5.0},
            transfer_in_mu=0.0,
            transfer_out_mu=0.0,
            policy=self.policy,
            price_shock={},
            weather_shock=-0.3,  # 低于 -0.15 阈值
            params=self.params,
        )
        spec = self.params.crops["rice"]
        expect_payout = (
            5.0 * spec["insured_yield"] * spec["price"] * self.params.insurance_payout_ratio
        )
        self.assertGreater(acct.insurance_payout, 0)
        self.assertAlmostEqual(acct.insurance_payout, expect_payout, places=6)

    def test_no_payout_in_normal_year(self):
        acct = compute_farmer_accounting(
            plan={"rice": 5.0},
            insured={"rice": 5.0},
            transfer_in_mu=0.0,
            transfer_out_mu=0.0,
            policy=self.policy,
            price_shock={},
            weather_shock=0.0,
            params=self.params,
        )
        self.assertEqual(acct.insurance_payout, 0.0)

    def test_land_transfer_income(self):
        acct = compute_farmer_accounting(
            plan={},
            insured={},
            transfer_in_mu=0.0,
            transfer_out_mu=8.0,
            policy=self.policy,
            price_shock={},
            weather_shock=0.0,
            params=self.params,
        )
        # 转出收入 = 8 亩 × (地租 500 + 转出补贴 0)
        self.assertAlmostEqual(acct.rent_income, 8.0 * self.params.rent_out_per_mu, places=6)

    def test_off_farm_quarter_income(self):
        acct = compute_farmer_accounting(
            plan={},
            insured={},
            transfer_in_mu=0.0,
            transfer_out_mu=0.0,
            policy=self.policy,
            price_shock={},
            weather_shock=0.0,
            off_farm_income_annual=40000.0,
            params=self.params,
        )
        self.assertAlmostEqual(acct.off_farm_income, 10000.0, places=6)  # 年/4


class TestVillageSummary(unittest.TestCase):
    def test_summary(self):
        a1 = FarmerAccounting(net_income=100.0, subsidy_income=10.0,
                              planted_area_mu=5.0, insured_area_mu=2.0)
        a2 = FarmerAccounting(net_income=300.0, subsidy_income=30.0,
                              planted_area_mu=0.0, insured_area_mu=0.0)
        s = village_summary([a1, a2], total_subsidy=40.0, weather_shock=-0.1)
        self.assertAlmostEqual(s["avg_net_income"], 200.0, places=6)
        self.assertAlmostEqual(s["avg_subsidy_income"], 20.0, places=6)
        self.assertAlmostEqual(s["insurance_coverage_rate"], 0.4, places=6)  # 2/5
        self.assertEqual(s["n_planting_farmers"], 1)  # 只有 a1 有种植
        self.assertEqual(s["total_subsidy"], 40.0)

    def test_summary_no_planting_first_step(self):
        # 首季农户尚未决策：全部 planted=0，coverage 为空列表，不能抛 StatisticsError
        a = FarmerAccounting(net_income=0.0, subsidy_income=0.0,
                             planted_area_mu=0.0, insured_area_mu=0.0)
        s = village_summary([a, a, a], total_subsidy=0.0, weather_shock=0.0)
        self.assertEqual(s["insurance_coverage_rate"], 0.0)
        self.assertEqual(s["n_planting_farmers"], 0)
        self.assertEqual(s["avg_planted_area"], 0.0)


if __name__ == "__main__":
    unittest.main()
