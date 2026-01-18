import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  Table,
  Tag,
  Space,
  Button,
  Input,
  Select,
  DatePicker,
  Badge,
  Tooltip,
  Alert,
  Radio,
} from 'antd';
import {
  SearchOutlined,
  EyeOutlined,
  ThunderboltOutlined,
  ReloadOutlined,
  ClockCircleOutlined,
  CalendarOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { Dayjs } from 'dayjs';
import { format } from 'date-fns';
import { clusterAPI } from '@/api/client';
import type { ExceptionCluster } from '@/types';
import { useAppStore } from '@/store';
import { useServiceContext } from '@/contexts/ServiceContext';

const { RangePicker } = DatePicker;

const Clusters = () => {
  const navigate = useNavigate();
  const { refreshIntervals } = useAppStore();
  const { selectedService } = useServiceContext();
  
  // Local state for filters (independent from global context)
  const [searchText, setSearchText] = useState('');
  const [statusFilter, setStatusFilter] = useState<'active' | 'skipped' | 'resolved' | 'all'>('all');
  const [timeFilterMode, setTimeFilterMode] = useState<'all' | 'preset' | 'custom'>('all');
  const [presetTimeFilter, setPresetTimeFilter] = useState<string>('24h');
  const [customDateRange, setCustomDateRange] = useState<[Dayjs | null, Dayjs | null] | null>(null);

  // Determine which time filter to use based on mode
  const getActiveTimeFilter = () => {
    if (timeFilterMode === 'all') {
      return undefined; // No time filter - show all
    } else if (timeFilterMode === 'preset') {
      return presetTimeFilter;
    } else if (timeFilterMode === 'custom' && customDateRange) {
      // For custom range, we'll use a special format
      const [start, end] = customDateRange;
      if (start && end) {
        return `custom:${start.toISOString()}:${end.toISOString()}`;
      }
    }
    return undefined;
  };

  const activeTimeFilter = getActiveTimeFilter();

  const { data: clusters, isLoading, refetch } = useQuery({
    queryKey: ['clusters', statusFilter, selectedService, activeTimeFilter],
    queryFn: () => clusterAPI.list(statusFilter, selectedService, undefined, activeTimeFilter),
    refetchInterval: refreshIntervals.clusters,
  });



  const severityColors = {
    critical: 'red',
    high: 'orange',
    medium: 'gold',
    low: 'blue',
  };

  type Severity = keyof typeof severityColors;
  
  const statusColors = {
    active: 'error',
    skipped: 'default',
    resolved: 'success',
  };

  type StatusType = keyof typeof statusColors;

  const columns: ColumnsType<ExceptionCluster> = [
    {
      title: 'Exception Type',
      dataIndex: 'exception_type',
      key: 'exception_type',
      render: (type, record) => (
        <div>
          <div style={{ fontWeight: 500, marginBottom: 4 }}>{type}</div>
          <div style={{ fontSize: 12, color: '#8c8c8c' }}>
            <code style={{ fontSize: 11 }}>{record.signature?.substring(0, 60) ?? 'N/A'}</code>
          </div>
        </div>
      ),
      width: 300,
    },
    {
      title: 'Logger Path',
      dataIndex: 'logger_path',
      key: 'logger_path',
      render: (loggerPath) => (
        <Tooltip title={loggerPath || 'Unknown'}>
          <code style={{ fontSize: 11, color: '#1890ff' }}>
            {loggerPath ? (
              loggerPath.length > 40 ? `...${loggerPath.slice(-40)}` : loggerPath
            ) : (
              <span style={{ color: '#999' }}>unknown</span>
            )}
          </code>
        </Tooltip>
      ),
      width: 200,
      ellipsis: true,
    },
    {
      title: 'Severity',
      dataIndex: 'severity',
      key: 'severity',
      render: (severity:Severity) => (
        <Tag color={severityColors[severity]} style={{ textTransform: 'uppercase' }}>
          {severity}
        </Tag>
      ),
      filters: [
        { text: 'Critical', value: 'critical' },
        { text: 'High', value: 'high' },
        { text: 'Medium', value: 'medium' },
        { text: 'Low', value: 'low' },
      ],
      onFilter: (value, record) => record.severity === value,
      width: 100,
    },
    {
      title: 'Count',
      dataIndex: 'count',
      key: 'count',
      render: (count) => (
        <Badge
          count={count}
          showZero
          style={{ backgroundColor: count > 50 ? '#cf1322' : '#52c41a' }}
        />
      ),
      sorter: (a, b) => a.count - b.count,
      width: 100,
    },
    {
      title: 'Services',
      dataIndex: 'services',
      key: 'services',
      render: (services) => {
        if (!services || services.length === 0) {
          return <span style={{ color: '#999' }}>No services</span>;
        }

        return (
          <Space size={4} wrap>
            {services.slice(0, 2).map((service: string) => (
              <Tag key={service} color="blue">
                {service}
              </Tag>
            ))}
            {services.length > 2 && <Tag>+{services.length - 2}</Tag>}
          </Space>
        );
      },
      width: 200,
    },
    {
      title: 'First Seen',
      dataIndex: 'first_seen',
      key: 'first_seen',
      render: (date) => (
        <Tooltip title={new Date(date).toLocaleString()}>
          {format(new Date(date), 'MMM dd, HH:mm')}
        </Tooltip>
      ),
      sorter: (a, b) => new Date(a.first_seen).getTime() - new Date(b.first_seen).getTime(),
      width: 120,
    },
    {
      title: 'Last Seen',
      dataIndex: 'last_seen',
      key: 'last_seen',
      render: (date) => (
        <Tooltip title={new Date(date).toLocaleString()}>
          {format(new Date(date), 'MMM dd, HH:mm')}
        </Tooltip>
      ),
      sorter: (a, b) => new Date(a.last_seen).getTime() - new Date(b.last_seen).getTime(),
      width: 120,
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: StatusType) => {
        const color = statusColors[status] || 'default';
        return (
          <Tag color={color} style={{ textTransform: 'capitalize' }}>
            {status || 'active'}
          </Tag>
        );
      },
      filters: [
        { text: 'Active', value: 'active' },
        { text: 'Skipped', value: 'skipped' },
        { text: 'Resolved', value: 'resolved' },
      ],
      onFilter: (value, record) => record.status === value,
      width: 100,
    },
    {
      title: 'RCA',
      dataIndex: 'has_rca',
      key: 'has_rca',
      render: (hasRca, record) => (
        <Space>
          {hasRca ? (
            <Tag color="green" icon={<ThunderboltOutlined />}>
              Available
            </Tag>
          ) : (
            <Tag color="default">Not Generated</Tag>
          )}
        </Space>
      ),
      filters: [
        { text: 'Has RCA', value: true },
        { text: 'No RCA', value: false },
      ],
      onFilter: (value, record) => record.has_rca === value,
      width: 130,
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_, record) => (
        <Space size="small">
          <Button
            type="text"
            icon={<EyeOutlined />}
            onClick={() => navigate(`/clusters/${record.cluster_id}`)}
          >
            View
          </Button>
          {record.has_rca && (
            <Button
              type="link"
              onClick={() => navigate(`/rca/${record.cluster_id}`)}
            >
              View RCA
            </Button>
          )}
        </Space>
      ),
      width: 150,
    },
  ];

  const filteredClusters = clusters?.filter((cluster) => {
    if (searchText && !cluster.exception_type.toLowerCase().includes(searchText.toLowerCase())) {
      return false;
    }
    return true;
  });

  return (
    <div style={{ maxWidth: '100%', overflowX: 'hidden' }}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 600 }}>Exception Clusters</h1>
        <p style={{ margin: '8px 0 0', color: '#8c8c8c' }}>
          Browse and analyze exception clusters across your services
        </p>
      </div>



      {/* Filters */}
      <Card style={{ marginBottom: 16 }}>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {/* Search and Status Filters */}
          <Space size="middle" wrap style={{ width: '100%' }}>
            <Input
              placeholder="Search exceptions..."
              prefix={<SearchOutlined />}
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              style={{ width: 300 }}
              allowClear
            />

            <Select
              placeholder="Filter by Status"
              style={{ width: 180 }}
              value={statusFilter}
              onChange={(value) => setStatusFilter(value)}
              options={[
                { label: 'All Exceptions', value: 'all' },
                { label: 'Active Only', value: 'active' },
                { label: 'Skipped', value: 'skipped' },
                { label: 'Resolved', value: 'resolved' },
              ]}
            />

            <Button icon={<ReloadOutlined />} onClick={() => refetch()}>
              Refresh
            </Button>
          </Space>

          {/* Time Filter Section */}
          <div>
            <div style={{ marginBottom: 8, fontWeight: 500 }}>
              <ClockCircleOutlined style={{ marginRight: 8 }} />
              Time Range Filter:
            </div>
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <Radio.Group 
                value={timeFilterMode} 
                onChange={(e) => setTimeFilterMode(e.target.value)}
                style={{ width: '100%' }}
              >
                <Space direction="vertical" size="small">
                  <Radio value="all">
                    <strong>All Time</strong> - Show all exceptions regardless of when they occurred
                  </Radio>
                  <Radio value="preset">
                    <strong>Preset Time Range</strong> - Filter by predefined time periods
                  </Radio>
                  <Radio value="custom">
                    <strong>Custom Date Range</strong> - Select specific start and end dates
                  </Radio>
                </Space>
              </Radio.Group>

              {/* Preset Time Filter Options */}
              {timeFilterMode === 'preset' && (
                <div style={{ marginLeft: 24, marginTop: 8 }}>
                  <Select
                    value={presetTimeFilter}
                    onChange={setPresetTimeFilter}
                    style={{ width: 250 }}
                    options={[
                      { label: 'Last 5 minutes', value: '5m' },
                      { label: 'Last 10 minutes', value: '10m' },
                      { label: 'Last 30 minutes', value: '30m' },
                      { label: 'Last 1 hour', value: '1h' },
                      { label: 'Last 6 hours', value: '6h' },
                      { label: 'Last 24 hours', value: '24h' },
                      { label: 'Last 7 days', value: '7d' },
                      { label: 'Last 30 days', value: '30d' },
                    ]}
                  />
                </div>
              )}

              {/* Custom Date Range Picker */}
              {timeFilterMode === 'custom' && (
                <div style={{ marginLeft: 24, marginTop: 8 }}>
                  <RangePicker
                    showTime
                    format="YYYY-MM-DD HH:mm:ss"
                    value={customDateRange}
                    onChange={(dates) => setCustomDateRange(dates)}
                    style={{ width: 400 }}
                    placeholder={['Start Date & Time', 'End Date & Time']}
                  />
                  {customDateRange && customDateRange[0] && customDateRange[1] && (
                    <div style={{ marginTop: 8, fontSize: 12, color: '#8c8c8c' }}>
                      <CalendarOutlined style={{ marginRight: 4 }} />
                      Showing exceptions from {customDateRange[0].format('MMM DD, YYYY HH:mm')} to {customDateRange[1].format('MMM DD, YYYY HH:mm')}
                    </div>
                  )}
                </div>
              )}
            </Space>
          </div>

          {/* Active Filter Summary */}
          {timeFilterMode !== 'all' && (
            <Alert
              message={
                timeFilterMode === 'preset'
                  ? `Filtering by: ${presetTimeFilter === '5m' ? 'Last 5 minutes' : 
                      presetTimeFilter === '10m' ? 'Last 10 minutes' :
                      presetTimeFilter === '30m' ? 'Last 30 minutes' :
                      presetTimeFilter === '1h' ? 'Last 1 hour' :
                      presetTimeFilter === '6h' ? 'Last 6 hours' :
                      presetTimeFilter === '24h' ? 'Last 24 hours' :
                      presetTimeFilter === '7d' ? 'Last 7 days' :
                      'Last 30 days'}`
                  : customDateRange && customDateRange[0] && customDateRange[1]
                    ? `Filtering by custom range: ${customDateRange[0].format('MMM DD, YYYY HH:mm')} - ${customDateRange[1].format('MMM DD, YYYY HH:mm')}`
                    : 'Select a date range'
              }
              type="info"
              showIcon
              closable
              onClose={() => setTimeFilterMode('all')}
            />
          )}
        </Space>
      </Card>

      {/* Table */}
      <Card>
        <Table
          columns={columns}
          dataSource={filteredClusters}
          loading={isLoading}
          rowKey="cluster_id"
          pagination={{
            pageSize: 20,
            showSizeChanger: true,
            showTotal: (total) => `Total ${total} clusters`,
          }}
          scroll={{ x: 1200 }}
        />
      </Card>
    </div>
  );
};

export default Clusters;
