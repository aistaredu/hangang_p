SELECT * FROM hangang_parking.parking_daily;

-- 100% 초과 데이터가 전체에서 몇 %인지
SELECT
    COUNT(*) AS total_rows,
    SUM(CASE WHEN d.daily_count > i.capacity THEN 1 ELSE 0 END) AS over_100,
    ROUND(SUM(CASE WHEN d.daily_count > i.capacity THEN 1 ELSE 0 END) / COUNT(*) * 100, 1) AS over_100_pct
FROM parking_daily d
JOIN parking_info i ON d.lot_id = i.id
WHERE d.daily_count > 0 AND i.capacity > 0;


-- 혼잡도 구간별로 몇 건인지
SELECT
    CASE
        WHEN d.daily_count / i.capacity * 100 <= 100 THEN '0-100%'
        WHEN d.daily_count / i.capacity * 100 <= 200 THEN '100-200%'
        WHEN d.daily_count / i.capacity * 100 <= 400 THEN '200-400%'
        ELSE '400%+'
    END AS range_group,
    COUNT(*) AS cnt
FROM parking_daily d
JOIN parking_info i ON d.lot_id = i.id
WHERE d.daily_count > 0 AND i.capacity > 0
GROUP BY range_group
ORDER BY MIN(d.daily_count / i.capacity * 100);

