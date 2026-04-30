import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { TrendingUp, DollarSign, Building2, Package } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { cn } from '../../lib/utils';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  PieChart, Pie, Cell
} from 'recharts';
import { useSienge } from '../../contexts/SiengeContext';
import { parseISO } from 'date-fns';
import { toMoney, translateStatusLabel } from '../financeiro/logic';

export function DashboardGeral() {
  const { orders, financialTitles, receivableTitles, selectedCompany, companies, buildings } = useSienge();

  const stats = useMemo(() => {
    const ordersArray = Array.isArray(orders) ? orders : [];
    const total = ordersArray.reduce((acc: number, curr: any) => acc + toMoney(curr.totalAmount), 0);
    const avg = ordersArray.length > 0 ? total / ordersArray.length : 0;
    
    const fTotal = financialTitles.reduce((acc: number, curr: any) => acc + toMoney(curr.amount), 0);
    const rTotal = receivableTitles.reduce((acc: number, curr: any) => acc + toMoney(curr.amount), 0);
    const balance = rTotal - fTotal;

    return { total, avg, fTotal, rTotal, balance };
  }, [orders, financialTitles, receivableTitles]);

  const chartData = useMemo(() => {
    const months = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
    const data = months.map(m => ({ name: m, valor: 0, financeiro: 0 }));
    const ordersArray = Array.isArray(orders) ? orders : [];
    
    ordersArray.forEach((order: any) => {
      if (order && order.date) {
        try {
          const d = parseISO(order.date);
          if (d && !isNaN(d.getTime())) {
            const month = d.getMonth();
            if (month >= 0 && month < 12) {
              data[month].valor += (order.totalAmount || 0);
            }
          }
        } catch {}
      }
    });

    financialTitles.forEach((title: any) => {
      if (title && title.dueDate) {
        try {
          const d = parseISO(title.dueDate);
          if (d && !isNaN(d.getTime())) {
            const month = d.getMonth();
            if (month >= 0 && month < 12) {
              data[month].financeiro += (title.amount || 0);
            }
          }
        } catch {}
      }
    });

    return data;
  }, [orders, financialTitles]);

  const orderStatusData = useMemo(() => {
    const map: Record<string, number> = {};
    const ordersArray = Array.isArray(orders) ? orders : [];
    ordersArray.forEach((o: any) => {
      const status = translateStatusLabel(o.status) || 'N/D';
      map[status] = (map[status] || 0) + 1;
    });
    return Object.entries(map).map(([name, value]) => ({ name, value })).sort((a,b) => b.value - a.value);
  }, [orders]);

  const activeBuildingCount = buildings.length;

  return (
    <motion.div key="db-geral" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} className="space-y-8">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-6">
        {[
          { label: selectedCompany !== 'all' ? `COMPRAS — ${companies.find((c: any) => String(c.id) === selectedCompany)?.name || 'Empresa'}` : 'COMPRAS EFETUADAS', value: `R$ ${stats.total.toLocaleString('pt-BR', { maximumFractionDigits: 0 })}`, icon: TrendingUp, color: 'orange' },
          { label: selectedCompany !== 'all' ? `SALDO — ${companies.find((c: any) => String(c.id) === selectedCompany)?.name || 'Empresa'}` : 'Saldo Financeiro', value: `R$ ${stats.balance.toLocaleString('pt-BR', { maximumFractionDigits: 0 })}`, icon: DollarSign, color: stats.balance >= 0 ? 'green' : 'red' },
          { label: 'Obras Ativas', value: activeBuildingCount, icon: Building2, color: 'orange' },
          { label: 'Total de Pedidos', value: orders.length, icon: Package, color: 'orange' }
        ].map((kpi, i) => (
          <Card key={i} className="bg-[#161618] border-white/5 shadow-2xl overflow-hidden relative group">
            <div className="absolute top-0 right-0 p-3 opacity-10 group-hover:opacity-20 transition-opacity"><kpi.icon size={40} className="text-orange-500" /></div>
            <CardHeader className="pb-2 p-4 sm:p-6">
              <CardDescription className="text-[9px] sm:text-[10px] font-black uppercase tracking-widest text-orange-500/70 leading-tight">{kpi.label}</CardDescription>
              <CardTitle className={cn("text-xl sm:text-3xl font-black tracking-tighter mt-1", kpi.color === 'red' ? 'text-red-500' : kpi.color === 'green' ? 'text-green-500' : 'text-white')}>{kpi.value}</CardTitle>
            </CardHeader>
            <div className="h-1 w-full bg-orange-600/20"><div className="h-full bg-orange-600 w-1/3" /></div>
          </Card>
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-8">
        <Card className="lg:col-span-2 bg-[#161618] border-white/5 shadow-2xl">
          <CardHeader><CardTitle className="text-lg font-black uppercase tracking-tight text-white">Evolução Histórica</CardTitle></CardHeader>
          <CardContent className="h-[220px] sm:h-[350px] pt-4">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="colorVal" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f97316" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#f97316" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#ffffff05" />
                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{fill: '#666', fontSize: 12}} />
                <YAxis axisLine={false} tickLine={false} tick={{fill: '#666', fontSize: 12}} tickFormatter={(v) => `R$${v/1000}k`} />
                <Tooltip formatter={(value: number) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value)} contentStyle={{ backgroundColor: '#161618', border: '1px solid rgba(255,255,255,0.1)' }} />
                <Legend />
                <Area type="monotone" dataKey="valor" name="Compras Globais" stroke="#f97316" strokeWidth={4} fillOpacity={1} fill="url(#colorVal)" />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card className="bg-[#161618] border-white/5 shadow-2xl">
          <CardHeader><CardTitle className="text-lg font-black uppercase tracking-tight text-white">Status dos Pedidos</CardTitle></CardHeader>
          <CardContent className="h-[220px] sm:h-[350px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={orderStatusData} cx="50%" cy="50%" innerRadius={60} outerRadius={80} paddingAngle={5} dataKey="value">
                  {orderStatusData.map((e, index) => <Cell key={index} fill={['#f97316', '#3b82f6', '#10b981', '#f59e0b', '#6366f1'][index % 5]} />)}
                </Pie>
                <Tooltip contentStyle={{ backgroundColor: '#161618', border: 'none', borderRadius: '8px' }} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </motion.div>
  );
}
